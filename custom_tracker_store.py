from __future__ import annotations
from asyncio.windows_events import NULL
import contextlib
from http.client import ImproperConnectionState
import itertools
import json
import logging
import datetime
import requests
from sqlite3 import Timestamp

from time import sleep
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Text,
    Union,
    TYPE_CHECKING,
    Generator,
    TypeVar,
    Generic,
)

import rasa.core.utils as core_utils
import rasa.shared.utils.cli
import rasa.shared.utils.common
import rasa.shared.utils.io
from rasa.core.brokers.broker import EventBroker
from rasa.core.constants import (
    POSTGRESQL_SCHEMA,
    POSTGRESQL_MAX_OVERFLOW,
    POSTGRESQL_POOL_SIZE,
)
from rasa.shared.core.domain import Domain
from rasa.shared.core.events import SessionStarted
from rasa.shared.core.trackers import (
    ActionExecuted,
    DialogueStateTracker,
    EventVerbosity,
)
from rasa.shared.nlu.constants import INTENT_NAME_KEY
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta

from rasa.core.tracker_store import TrackerStore, _create_sequence, create_engine_kwargs, ensure_schema_exists


logger = logging.getLogger(__name__)

# will relevant questions be available from the chatbot outside notifications?
questionnaire_per_usecase = {
    "ms": ["MSdomainI", "MSdomainII", "MSdomainIII", "MSdomainIV", "MSdomainV"],
    "stroke": ["activLim", "muscletone", "dizzNbalance", "eatinghabits", "psqi", "coast", "STROKEdomainIII", "STROKEdomainIV", "STROKEdomainV"]
}

#"ms_orig": ["MSdomainI", "MSdomainII_1M", "MSdomainII_3M", "MSdomainIII_1W", "MSdomainIII_2W", "MSdomainIV", "MSdomainV"],
                        

class CustomSQLTrackerStore(TrackerStore):
    """Store which can save and retrieve trackers from an SQL database. Based on rasa's original SQLTrackerStore"""

    from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta

    Base: DeclarativeMeta = declarative_base()

    class SQLEvent(Base):
        """Represents an event in the SQL Tracker Store."""

        __tablename__ = "events"
        # `create_sequence` is needed to create a sequence for databases that
        # don't autoincrement Integer primary keys (e.g. Oracle)
        id = sa.Column(sa.Integer, _create_sequence(__tablename__), primary_key=True)
        sender_id = sa.Column(sa.String(255), nullable=False, index=True)
        message = sa.Column(sa.String(255))
        #sentiment = sa.Column(sa.Text)
        type_name = sa.Column(sa.String(255), nullable=False)
        timestamp = sa.Column(sa.Float)
        intent_name = sa.Column(sa.String(255))
        action_name = sa.Column(sa.String(255))
        data = sa.Column(sa.Text)

    class SQLQuestState(Base):
        """Represents a questionnaire event in the SQL Tracker Store."""

        __tablename__ = "questionnaires_state"
        # `create_sequence` is needed to create a sequence for databases that
        # don't autoincrement Integer primary keys (e.g. Oracle)
        id = sa.Column(sa.Integer, _create_sequence(__tablename__), primary_key=True)
        sender_id = sa.Column(sa.String(255), nullable=False, index=True)
        questionnaire_name = sa.Column(sa.String(255), nullable=False)
        available_at = sa.Column(sa.Float)
        state = sa.Column(sa.String(255), nullable=False)
        timestamp_start = sa.Column(sa.Float)
        timestamp_end = sa.Column(sa.Float)
        answers = sa.Column(sa.Text)

    class SQLUserID(Base):
        """Represents a user id event in the SQL Tracker Store."""

        __tablename__ = "userIDs"
        # `create_sequence` is needed to create a sequence for databases that
        # don't autoincrement Integer primary keys (e.g. Oracle)
        id = sa.Column(sa.Integer, _create_sequence(__tablename__), primary_key=True)
        sender_id = sa.Column(sa.String(255), nullable=False, index=True)
        usecase = sa.Column(sa.String(255), nullable=False)
        onboarding_timestamp = sa.Column(sa.Float)

    # class SQLSchedule(Base):
    #     """Represents an event in the SQL Tracker Store."""

    #     __tablename__ = "schedule"
    #     id = sa.Column(sa.Integer, _create_sequence(__tablename__), primary_key=True)
    #     usecase = sa.Column(sa.String(255))
    #     questionnaire_name = sa.Column(sa.String(255))
    #     questionnaire_abvr = sa.Column(sa.String(255))
    #     frequencyInDays = sa.Column(sa.INT)
    #     lifespanInDays = sa.Column(sa.INT)

    def __init__(
        self,
        domain: Optional[Domain] = None,
        dialect: Text = "sqlite",
        host: Optional[Text] = None,
        port: Optional[int] = None,
        db: Text = "rasa.db",
        username: Text = None,
        password: Text = None,
        event_broker: Optional[EventBroker] = None,
        login_db: Optional[Text] = None,
        query: Optional[Dict] = None,
        **kwargs: Dict[Text, Any],
    ) -> None:
        import sqlalchemy.exc

        engine_url = self.get_db_url(
            dialect, host, port, db, username, password, login_db, query
        )

        self.engine = sa.create_engine(engine_url, **create_engine_kwargs(engine_url))

        logger.debug(
            f"Attempting to connect to database via '{repr(self.engine.url)}'."
        )

        # Database might take a while to come up
        while True:
            try:
                # if `login_db` has been provided, use current channel with
                # that database to create working database `db`
                if login_db:
                    self._create_database_and_update_engine(db, engine_url)

                try:
                    self.Base.metadata.create_all(self.engine)
                except (
                    sqlalchemy.exc.OperationalError,
                    sqlalchemy.exc.ProgrammingError,
                ) as e:
                    # Several Rasa services started in parallel may attempt to
                    # create tables at the same time. That is okay so long as
                    # the first services finishes the table creation.
                    logger.error(f"Could not create tables: {e}")

                self.sessionmaker = sa.orm.session.sessionmaker(bind=self.engine)
                break
            except (
                sqlalchemy.exc.OperationalError,
                sqlalchemy.exc.IntegrityError,
            ) as error:

                logger.warning(error)
                sleep(5)

        logger.debug(f"Connection to SQL database '{db}' successful.")

        super().__init__(domain, event_broker, **kwargs)

    @staticmethod
    def get_db_url(
        dialect: Text = "sqlite",
        host: Optional[Text] = None,
        port: Optional[int] = None,
        db: Text = "rasa.db",
        username: Text = None,
        password: Text = None,
        login_db: Optional[Text] = None,
        query: Optional[Dict] = None,
    ) -> Union[Text, "URL"]:
        """Build an SQLAlchemy `URL` object representing the parameters needed
        to connect to an SQL database.

        Args:
            dialect: SQL database type.
            host: Database network host.
            port: Database network port.
            db: Database name.
            username: User name to use when connecting to the database.
            password: Password for database user.
            login_db: Alternative database name to which initially connect, and create
                the database specified by `db` (PostgreSQL only).
            query: Dictionary of options to be passed to the dialect and/or the
                DBAPI upon connect.

        Returns:
            URL ready to be used with an SQLAlchemy `Engine` object.
        """
        from urllib import parse

        # Users might specify a url in the host
        if host and "://" in host:
            # assumes this is a complete database host name including
            # e.g. `postgres://...`
            return host
        elif host:
            # add fake scheme to properly parse components
            parsed = parse.urlsplit(f"scheme://{host}")

            # users might include the port in the url
            port = parsed.port or port
            host = parsed.hostname or host

        return sa.engine.url.URL(
            dialect,
            username,
            password,
            host,
            port,
            database=login_db if login_db else db,
            query=query,
        )

    def _create_database_and_update_engine(self, db: Text, engine_url: "URL") -> None:
        """Creates database `db` and updates engine accordingly."""
        from sqlalchemy import create_engine

        if not self.engine.dialect.name == "postgresql":
            rasa.shared.utils.io.raise_warning(
                "The parameter 'login_db' can only be used with a postgres database.",
            )
            return

        self._create_database(self.engine, db)
        self.engine.dispose()
        engine_url = sa.engine.url.URL(
            drivername=engine_url.drivername,
            username=engine_url.username,
            password=engine_url.password,
            host=engine_url.host,
            port=engine_url.port,
            database=db,
            query=engine_url.query,
        )
        self.engine = create_engine(engine_url)

    @staticmethod
    def _create_database(engine: "Engine", database_name: Text) -> None:
        """Create database `db` on `engine` if it does not exist."""
        import sqlalchemy.exc

        conn = engine.connect()

        matching_rows = (
            conn.execution_options(isolation_level="AUTOCOMMIT")
            .execute(
                sa.text(
                    "SELECT 1 FROM pg_catalog.pg_database "
                    "WHERE datname = :database_name"
                ),
                database_name=database_name,
            )
            .rowcount
        )

        if not matching_rows:
            try:
                conn.execute(f"CREATE DATABASE {database_name}")
            except (
                sqlalchemy.exc.ProgrammingError,
                sqlalchemy.exc.IntegrityError,
            ) as e:
                logger.error(f"Could not create database '{database_name}': {e}")

        conn.close()

    @contextlib.contextmanager
    def session_scope(self) -> Generator["Session", None, None]:
        """Provide a transactional scope around a series of operations."""
        session = self.sessionmaker()
        try:
            ensure_schema_exists(session)
            yield session
        except ValueError as e:
            rasa.shared.utils.cli.print_error_and_exit(
                f"Requested PostgreSQL schema '{e}' was not found in the database. To "
                f"continue, please create the schema by running 'CREATE DATABASE {e};' "
                f"or unset the '{POSTGRESQL_SCHEMA}' environment variable in order to "
                f"use the default schema. Exiting application."
            )
        finally:
            session.close()


    # @event.listens_for(SQLSchedule.__table__, 'after_create')
    # def _create_schedule(self):
    #     """Populated the schedule table after is created"""
    #     with self.session_scope as session:
            


    def keys(self) -> Iterable[Text]:
        """Returns sender_ids of the SQLTrackerStore"""
        with self.session_scope() as session:
            sender_ids = session.query(self.SQLEvent.sender_id).distinct().all()
            return [sender_id for (sender_id,) in sender_ids]

    def retrieve(self, sender_id: Text) -> Optional[DialogueStateTracker]:
        # TODO: Remove this in Rasa Open Source 3.0 along with the
        # deprecation warning in the constructor
        if self.retrieve_events_from_previous_conversation_sessions:
            return self.retrieve_full_tracker(sender_id)

        return self._retrieve(sender_id, fetch_events_from_all_sessions=False)

    def retrieve_full_tracker(
        self, conversation_id: Text
    ) -> Optional[DialogueStateTracker]:
        return self._retrieve(conversation_id, fetch_events_from_all_sessions=True)

    def _retrieve(
        self, sender_id: Text, fetch_events_from_all_sessions: bool
    ) -> Optional[DialogueStateTracker]:
        with self.session_scope() as session:

            serialised_events = self._event_query(
                session,
                sender_id,
                fetch_events_from_all_sessions=fetch_events_from_all_sessions,
            ).all()

            events = [json.loads(event.data) for event in serialised_events]

            if self.domain and len(events) > 0:
                logger.debug(f"Recreating tracker from sender id '{sender_id}'")
                return DialogueStateTracker.from_dict(
                    sender_id, events, self.domain.slots
                )
            else:
                logger.debug(
                    f"Can't retrieve tracker matching "
                    f"sender id '{sender_id}' from SQL storage. "
                    f"Returning `None` instead."
                )
                return None

    def _event_query(
        self, session: "Session", sender_id: Text, fetch_events_from_all_sessions: bool
    ) -> "Query":
        """Provide the query to retrieve the conversation events for a specific sender.

        Args:
            session: Current database session.
            sender_id: Sender id whose conversation events should be retrieved.
            fetch_events_from_all_sessions: Whether to fetch events from all
                conversation sessions. If `False`, only fetch events from the
                latest conversation session.

        Returns:
            Query to get the conversation events.
        """
        # Subquery to find the timestamp of the latest `SessionStarted` event
        session_start_sub_query = (
            session.query(sa.func.max(self.SQLEvent.timestamp).label("session_start"))
            .filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.type_name == SessionStarted.type_name,
            )
            .subquery()
        )

        event_query = session.query(self.SQLEvent).filter(
            self.SQLEvent.sender_id == sender_id
        )
        if not fetch_events_from_all_sessions:
            event_query = event_query.filter(
                # Find events after the latest `SessionStarted` event or return all
                # events
                sa.or_(
                    self.SQLEvent.timestamp >= session_start_sub_query.c.session_start,
                    session_start_sub_query.c.session_start.is_(None),
                )
            )

        return event_query.order_by(self.SQLEvent.timestamp)

    def _questionnaire_query(
        self, session: "Session", sender_id: Text, questionnaire_name: Text,
    ) -> "Query":
        """Provide the query to retrieve the questions and responses events for a specific sender for a specific questionnaire.

        Args:
            session: Current database session.
            sender_id: Sender id whose conversation events should be retrieved.
            timestamp: timestamp after when to search for these events
            questionnaire_name: The name of the questionnaire whose questions and responses should be retrieved.

        Returns:
            Query to get the questions and responses events.
        """
        # Subquery to find the timestamp of the latest `SessionStarted` event
        # latest_questionnaire_sub_query = (
        #     session.query(sa.func.max(self.SQLQuestState.timestamp).label(questionnaire_name))
        #     .filter(
        #         self.SQLEvent.sender_id == sender_id,
        #     )
        #     .subquery()
        # )

        # different time per pilot or save in specific timezone

        latest_questionnaire_sub_query = (
            session.query(sa.func.max(self.SQLEvent.timestamp).label("questionnaire_start"))
            .filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.intent_name == questionnaire_name+"_start",
                self.SQLEvent.type_name == "user",
                #self.SQLEvent.timestamp >= timestamp,
            )
            .subquery()
        )

        # latest_questionnaire_sub_query = session.query(sa.func.max(self.SQLEvent.timestamp)).filter(
        #         self.SQLEvent.sender_id == sender_id,
        #         self.SQLEvent.intent_name == questionnaire_name+"_start",
        #         self.SQLEvent.type_name == "user",
        #         #self.SQLEvent.timestamp >= timestamp,
        #     ).first()

        #print("ff",latest_questionnaire_sub_query[0])
        # this returns a tuple in the form (1655132361.3270664,)
        latest_start_time = session.query(sa.func.min(self.SQLEvent.timestamp)).filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.action_name.ilike("requested_slot"),
                self.SQLEvent.type_name == "slot",
                self.SQLEvent.timestamp > latest_questionnaire_sub_query.c.questionnaire_start,
            ).first()[0]

        cancel_request_timestamp = session.query(sa.func.min(self.SQLEvent.timestamp)).filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.intent_name == "cancel",
                self.SQLEvent.type_name == "user",
                self.SQLEvent.timestamp >= latest_start_time,
            ).first()
        print(cancel_request_timestamp)
        if cancel_request_timestamp[0] is not None:
            latest_end_time = cancel_request_timestamp[0]
        else:
            latest_end_time = session.query(sa.func.max(self.SQLEvent.timestamp)).filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.type_name == "slot",
                self.SQLEvent.action_name.ilike(questionnaire_name+"_%"),
                self.SQLEvent.timestamp > latest_start_time,
            ).first()[0]

        print(latest_start_time, latest_end_time)
        question_events = session.query(self.SQLEvent).filter(
            self.SQLEvent.sender_id == sender_id,
            #self.SQLEvent.timestamp >= latest_questionnaire_sub_query.c.questionnaire_start,
            #self.SQLEvent.timestamp.between(latest_start_time, latest_end_time),
            self.SQLEvent.timestamp >= latest_start_time,
            self.SQLEvent.timestamp < latest_end_time,
            self.SQLEvent.type_name == "bot",
        ).order_by(self.SQLEvent.timestamp).all()

        slot_events = session.query(self.SQLEvent).filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.type_name == "slot",
                self.SQLEvent.timestamp.between(latest_start_time, latest_end_time),
                #self.SQLEvent.action_name.notlike("utter_"+questionnaire_name),
                #self.SQLEvent.action_name.notlike(questionnaire_name+"_form"),
                self.SQLEvent.action_name.ilike(questionnaire_name+"_%")
                ).order_by(self.SQLEvent.timestamp).all()

        print(len(question_events))
        print("agree", len(question_events)==len(slot_events))
        return question_events, slot_events

    def _questionnaire_state_query(
        self, session: "Session", sender_id: Text, timestamp: float, questionnaire_name: Text=None):
        """Provide the query to retrieve the questionnaire state events for a specific sender.

        Args:
            session: Current database session.
            sender_id: Sender id whose conversation events should be retrieved.
            questionnaire_name: The name of the questionnaire whose questions and responses should be retrieved.


        Returns:
            One database row entry.
        """
        # available_questionnaire_sub_query = (session.query(self.SQLQuestState.state).label("available_state")).filter(
        #     sa.or_(
        #         self.SQLQuestState.state == "available",
        #         self.SQLQuestState.state == "pending",
        #     )).subquery()

        if questionnaire_name:
            database_entries = (
                session.query(self.SQLQuestState)
                .filter(
                    self.SQLQuestState.sender_id == sender_id,
                    self.SQLQuestState.questionnaire_name == questionnaire_name,
                    self.SQLQuestState.state.in_(["available", "pending"]),
                    self.SQLQuestState.available_at <= timestamp,
                )
            ).order_by(self.SQLQuestState.available_at)
        else: 
            database_entries = (
                session.query(self.SQLQuestState)
                .filter(
                    self.SQLQuestState.sender_id == sender_id,
                    self.SQLQuestState.state.in_(["available", "pending"]),
                    self.SQLQuestState.available_at <= timestamp,
                )
            ).order_by(self.SQLQuestState.available_at)
        
        return database_entries


    def _sentiment_query(
        self, session: "Session", sender_id: Text) -> "Query":
        """Provide the query to retrieve the sender message events for a specific sender which contain sentiment 
            and are not questionnaire-related.

        Args:
            session: Current database session.
            sender_id: Sender id whose conversation events should be retrieved.

        Returns:
            Query to get the user message events
        """
        # Subquery to find the timestamp of the latest `SessionStarted` event
        session_start_sub_query = (
            session.query(sa.func.max(self.SQLEvent.timestamp).label("session_start"))
            .filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.type_name == SessionStarted.type_name,
            )
            .subquery()
        )

        sentiment_entries = session.query(self.SQLEvent).filter(
            self.SQLEvent.sender_id == sender_id,
            self.SQLEvent.type_name == "slot",
            self.SQLEvent.action_name == "sentiment",
            self.SQLEvent.timestamp >= session_start_sub_query.c.session_start,
        ).order_by(self.SQLEvent.timestamp)

        sentiment_timestamps = [entry.timestamp for entry in sentiment_entries]
        message_entries = session.query(self.SQLEvent).filter(
            self.SQLEvent.sender_id == sender_id,
            self.SQLEvent.type_name == "user",
            self.SQLEvent.timestamp.in_(sentiment_timestamps),
        ).order_by(self.SQLEvent.timestamp)

        return message_entries

    def _first_time_of_day_query(
        self, session: "Session", sender_id: Text) -> "Query":
        """Query to retrieve whether is the first time of day the user was greeted by the agent (i.e. talked to the agent)

        Args:
            session: Current database session.
            sender_id: Sender id whose conversation events should be retrieved.

        Returns:
            Boolean, True=first time, False=not first time
        """
        today = datetime(datetime.today().year, datetime.today().month, datetime.today().day).timestamp()
        return session.query(self.SQLEvent).filter(
            self.SQLEvent.sender_id == sender_id,
            self.SQLEvent.type_name == "action",
            self.SQLEvent.action_name == "action_utter_how_are_you",
            self.SQLEvent.timestamp >= today,
        ) is None


    def save(self, tracker: DialogueStateTracker) -> None:
        """Update database with events from the current conversation."""

        if self.event_broker:
            self.stream_events(tracker)

        with self.session_scope() as session:
            # only store recent events
            events = self._additional_events(session, tracker)

            for event in events:
                data = event.as_dict()
                #if event.type_name == "action" and event.action_name=="action_listen":
                #    continue                
                
                intent = (
                    data.get("parse_data", {}).get("intent", {}).get(INTENT_NAME_KEY)
                )                    
                action = data.get("name")
                timestamp = data.get("timestamp")
                message = data.get("text")
                sender_id=tracker.sender_id
                # if event.type_name == "user":
                #     sentiment = {
                #         "value": data.get("parse_data", {}).get("entities", {})[0].get("value", ""),
                #         "confidence": data.get("parse_data", {}).get("entities", {})[0].get("confidence", "")
                #     }
                # else:
                #     sentiment = None

                # noinspection PyArgumentList
                session.add(
                    self.SQLEvent(
                        sender_id=sender_id,
                        message=message,
                        #sentiment=json.dumps(sentiment),
                        type_name=event.type_name,
                        timestamp=timestamp,
                        intent_name=intent,
                        action_name=action,
                        data=json.dumps(data),
                    )
                )                 

            session.commit()

        logger.debug(f"Tracker with sender_id '{tracker.sender_id}' stored to database")

    def _additional_events(
        self, session: "Session", tracker: DialogueStateTracker
    ) -> Iterator:
        """Return events from the tracker which aren't currently stored."""
        number_of_events_since_last_session = self._event_query(
            session,
            tracker.sender_id,
            fetch_events_from_all_sessions=(
                self.retrieve_events_from_previous_conversation_sessions
            ),
        ).count()

        return itertools.islice(
            tracker.events, number_of_events_since_last_session, len(tracker.events)
        )

    def saveRelevantQuestionsAnswers(self, sender_id, domain_name, tracker: DialogueStateTracker) -> None:
        """Update database with answers from a specific domain of relevant questions."""

        if self.event_broker:
            self.stream_events(tracker)

        with self.session_scope() as session:
            q_events, s_events  = self._questionnaire_query(session, sender_id, domain_name)
            question_events = [json.loads(event.data) for event in q_events]
            slot_events = [json.loads(event.data) for event in s_events]
            answers_data = {}

            for i, (question_data, slot_data) in enumerate(zip(question_events, slot_events)):
                if i==0:
                    init_timestamp = slot_data.get("timestamp")
                timestamp = slot_data.get("timestamp")

                # example: {q1: {"question": "How difficult is it..?", "answer": "very", "timestamp": }}
                answers_data[slot_data.get("name")] = {"question": question_data.get("text"), "answer": slot_data.get("value"), "timestamp": timestamp}

            
            session.add(
                self.SQLQuestState(
                    sender_id=sender_id,
                    questionnaire_name=domain_name,
                    available_at=init_timestamp,
                    state="finished",
                    timestamp_start=init_timestamp,
                    timestamp_end=timestamp,
                    answers=json.dumps(answers_data),                          
                    )
                )

            session.commit()

        logger.debug(f"Relevant questions answers with sender_id '{tracker.sender_id}' stored to database")


    def saveQuestionnaireAnswers(self, sender_id, questionnaire_name, isFinished: bool, tracker: DialogueStateTracker) -> None:
        """Update database with answers from a specific questionnaire."""

        class UniqueDict(dict):
            def __setitem__(self, key, value):
                if key not in self:
                    dict.__setitem__(self, key, value)
                else:
                    raise print("Key already exists")

        if self.event_broker:
            self.stream_events(tracker)

        with self.session_scope() as session:
            q_events, s_events  = self._questionnaire_query(session, sender_id, questionnaire_name)
            question_events = [json.loads(event.data) for event in q_events]
            slot_events = [json.loads(event.data) for event in s_events]
            print(slot_events)
            print(s_events)
            answers_data = UniqueDict()

            for i, (question_data, slot_data) in enumerate(zip(question_events, slot_events)):
                print(question_data, slot_data)
                if i==0:
                    init_timestamp = slot_data.get("timestamp")
                timestamp = slot_data.get("timestamp")

                try:
                    question_number = slot_data.get("name").split("Q")[1]
                except:
                    question_number = slot_data.get("name").split("activLim_")[1]
                
                # example: {q1: {"question": "How difficult is it..?", "answer": "very", "timestamp": }}
                answers_data[question_number] = {"question": question_data.get("text"), "answer": slot_data.get("value"), "timestamp": datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%dT%H:%M:%SZ")}

            try:
                database_entry = self._questionnaire_state_query(session, sender_id, init_timestamp, questionnaire_name).first()
                if database_entry.state=="available":
                    database_entry.timestamp_start=init_timestamp
                    database_entry.answers = json.dumps(answers_data)
                elif database_entry.state=="pending":
                    previous_answers = json.loads(database_entry.answers)
                    answers_data.update(previous_answers)
                    database_entry.answers = json.dumps({key: value for (key, value) in answers_data.items()})
                if isFinished:
                    database_entry.timestamp_end=timestamp
                    database_entry.state="finished"
                    #save to ontology
                    #saveQuestToOntology(database_entry)
                    #reset row
                    database_entry.available_at= (datetime.datetime.fromtimestamp(database_entry.available_at)+datetime.timedelta(days=4)).timestamp()
                    database_entry.state="available"
                    database_entry.timestamp_start=None
                    database_entry.timestamp_end=None # this seems to not be used
                    database_entry.answers = None
                else:
                    database_entry.state="pending"
            except:
                print("Error: no such entry in database table 'questionnaires_state'.")

            session.commit()

        logger.debug(f"Questionnaire answers with sender_id '{tracker.sender_id}' stored to database")

    def getSpecificQuestionnaireAvailability(self, sender_id, current_datetime, questionnaire_name) -> bool:
        current_timestamp = current_datetime.timestamp()
        with self.session_scope() as session:
            isAvailable = self._questionnaire_state_query(session, sender_id, current_timestamp, questionnaire_name).first() is None
        return isAvailable

    def isFirstTimeToday(self, sender_id) -> bool:
        with self.session_scope() as session:
            isFirstTime = self._first_time_of_day_query(session, sender_id) 
        return isFirstTime

    def getAvailableQuestionnaires(self, sender_id, current_datetime) -> List[str]:
        """ Retrieve currentlt available questionnaires"""
        available_questionnaires, reset_questionnaires = [],[]
        current_timestamp = current_datetime.timestamp()
        with self.session_scope() as session:
            database_entries = self._questionnaire_state_query(session, sender_id, current_timestamp).all()
            for entry in database_entries:
                # this step might need to happen somewhere else, myb automatically
                # checks whether 2 days has passed after the questionnaire was first available
                time_limit = (datetime.datetime.fromtimestamp(entry.available_at)+datetime.timedelta(days=2)).timestamp()
                if time_limit < current_datetime.timestamp():
                    entry.state = "incomplete"
                    # save to ontology
                    #saveQuestToOntology(entry)
                    # reset
                    entry.available_at= (datetime.datetime.fromtimestamp(entry.available_at)+datetime.timedelta(days=4)).timestamp()
                    entry.state="available"
                    entry.timestamp_start=None
                    entry.timestamp_end=None
                    entry.answers = None
                    # questionnaires that are passed the time limit need to be reset
                    reset_questionnaires.append(entry.questionnaire_name)
                else:
                    #if entry.state != "pending":
                        # questionnaires that were already completed in a previous session and need to be reset
                        #reset_questionnaires.append(entry.questionnaire_name)
                    available_questionnaires.append(entry.questionnaire_name)
            session.commit()
        return available_questionnaires, reset_questionnaires 

    def saveQuestToOntology(self, database_entry):
        pass


    def reset(self, database_entry):
        pass


    def saveToOntology(self,sender_id):
        ontology_data = {"user_id": sender_id, "source": "Conversational Agent", "observations" : []}
        with self.session_scope() as session:
            message_entries = self._sentiment_query(session, sender_id)
            for message in message_entries:
                message_data = json.loads(message.data)
                print(datetime.datetime.fromtimestamp(message.timestamp).strftime("%Y-%m-%dT%H:%M:%SZ"))
                sentiment = json.loads(message_data.get("parse_data", {}).get("entities", {}).get("value"))
                data = {"sentiment_scores": [sentiment[0]],
                    "timestamp": datetime.datetime.fromtimestamp(message.timestamp).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "explanation": message.message}
                print(data)
                ontology_data["observations"].append(data)

        #TODO:send to ontology

    def checkUserID(self, sender_id):
        """ Checks if the specific user id is in the database. If not it adds it"""
        with self.session_scope() as session:
            exists = session.query(self.SQLUserID).filter(self.SQLUserID.sender_id == sender_id).first() is not None
            if not exists:
                #temp
                usecase = sender_id[:len(sender_id)-2]
                if usecase not in questionnaire_per_usecase.keys():
                    return
                now = datetime.datetime.now() 
                session.add(
                    self.SQLUserID(
                        sender_id=sender_id,
                        usecase=usecase,
                        onboarding_timestamp=now.timestamp()                        
                    )
                )

                # add the corresponding questionnaires based on the usecase
                for questionnaire in questionnaire_per_usecase[usecase]:
                    now = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    #timestamp = (now + datetime.timedelta(days=1)).timestamp()
                    timestamp = now.timestamp()
                    print(timestamp)
                    session.add(
                        self.SQLQuestState(
                            sender_id=sender_id,
                            questionnaire_name=questionnaire,
                            available_at=timestamp,
                            state="available",
                            timestamp_start=None,
                            timestamp_end=None,
                            answers=None,                          
                    )
                )

            session.commit()
   


# get the name of the active form 
#active_loop = tracker.active_loop.get(‘name’)

if __name__ == "__main__":
    ts = CustomSQLTrackerStore(db="demo.db")

    #print(ts.getAvailableQuestionnaires("stroke00",datetime.datetime.now()))
    #print(ts.saveQuestionnaireAnswers("stroke03", "activLim", False))
    now = datetime.datetime.now().timestamp()
    print(1654808400<now)
    with ts.session_scope() as session:
        #question_events = ts._questionnaire_state_query(session, "stroke05", now, "activLim")
        #print(question_events.first().state)
        #q = [json.loads(event.data) for event in question_events]
        #print(q)
        question_events, slot = ts._questionnaire_query(session, "stroke19", "STROKEdomainIII")
        print([json.loads(event.data) for event in question_events])
        print([json.loads(event.data) for event in slot])




  


