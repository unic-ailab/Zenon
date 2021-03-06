from __future__ import annotations
import contextlib
from http.client import ImproperConnectionState
import itertools
import json
import logging
import datetime
import requests
import pandas as pd
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
    "MS": ["MSdomainI", "MSdomainII_1M", "MSdomainII_3M", "MSdomainIII_1W", "MSdomainIII_2W", "MSdomainIV_Daily", "MSdomainIV_1W", "MSdomainV"],
    "STROKE": ["activLim", "muscletone", "dizzNbalance", "eatinghabits", "psqi", "coast", "STROKEdomainIII", "STROKEdomainIV", "STROKEdomainV"]
}

schedule_df = pd.read_csv("pilot_schedule.csv")                       

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

        #not so great approach
        if  questionnaire_name in ["MSdomainIII_2W", "MSdomainII_3M"]:
            latest_questionnaire_sub_query = (
                session.query(sa.func.max(self.SQLEvent.timestamp).label("questionnaire_start"))
                .filter(
                    self.SQLEvent.sender_id == sender_id,
                    self.SQLEvent.action_name == "action_questionnaire_completed_first_part",
                    self.SQLEvent.type_name == "action",
                    #self.SQLEvent.timestamp >= timestamp,
                )
                .subquery()
            )
        else:
            latest_questionnaire_sub_query = (
                session.query(sa.func.max(self.SQLEvent.timestamp).label("questionnaire_start"))
                .filter(
                    self.SQLEvent.sender_id == sender_id,
                    self.SQLEvent.intent_name == questionnaire_name +"_start",
                    self.SQLEvent.type_name == "user",
                    #self.SQLEvent.timestamp >= timestamp,
                )
                .subquery()
            )

        # latest_questionnaire_sub_query1 = session.query(self.SQLEvent.timestamp).filter(
        #         self.SQLEvent.sender_id == sender_id,
        #         self.SQLEvent.action_name == "action_questionnaire_completed_first_part",
        #         self.SQLEvent.type_name == "action",
        #         #self.SQLEvent.timestamp >= timestamp,
        #     ).first()[0]
        # print(latest_questionnaire_sub_query1)

        # this returns a tuple in the form (1655132361.3270664,)
        latest_start_time = session.query(sa.func.min(self.SQLEvent.timestamp)).filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.action_name.ilike("requested_slot"),
                self.SQLEvent.type_name == "slot",
                self.SQLEvent.timestamp > latest_questionnaire_sub_query.c.questionnaire_start,
            ).first()[0]

        print(latest_start_time)
        cancel_request_timestamp = session.query(sa.func.min(self.SQLEvent.timestamp)).filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.intent_name == "cancel",
                self.SQLEvent.type_name == "user",
                self.SQLEvent.timestamp >= latest_start_time,
            ).first()[0]
        print(cancel_request_timestamp)
        if cancel_request_timestamp is not None:
            latest_end_time = cancel_request_timestamp
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

    def _questionnaire_answers_query(
        self, session: "Session", sender_id: Text, questionnaire_name: Text, onlyFinished:bool=False, previous: int=0):
        """Provide the query to retrieve a specific questionnaire's answers for a specific sender.

        Args:
            session: Current database session.
            sender_id: Sender id whose conversation events should be retrieved.
            questionnaire_name: The name of the questionnaire whose questions and responses should be retrieved.
            onlyFinished: boolean, whether to search for only finished questionnaires or also pending questionnaires
            previous: integer, how many questionnaires before the latest one to retrieve


        Returns:
            - latest questionnaire answers database cell
            - latest questionnaire answers database cell, list of the k-previous questionnaire answers database cell
        """
        if onlyFinished:
            states = ["finished"]
        else:
            states = ["finished", "pending"]

        latest_questionnaire_sub_query = session.query(sa.func.max(self.SQLQuestState.timestamp_end).label("latest_timestamp")).filter(
            sa.and_(
                self.SQLQuestState.sender_id == sender_id,
                self.SQLQuestState.questionnaire_name == questionnaire_name,
                self.SQLQuestState.state.in_(states),
            )).subquery()

        answers_entry = (
                session.query(self.SQLQuestState)
                .filter(
                    self.SQLQuestState.sender_id == sender_id,
                    self.SQLQuestState.questionnaire_name == questionnaire_name,
                    self.SQLQuestState.state.in_(states),
                    self.SQLQuestState.timestamp_end >= latest_questionnaire_sub_query.c.latest_timestamp,
                )
            ).first()
        if previous > 0:
            previous_answers_entries = (
                session.query(self.SQLQuestState.answers)
                .filter(
                    self.SQLQuestState.sender_id == sender_id,
                    self.SQLQuestState.questionnaire_name == questionnaire_name,
                    self.SQLQuestState.state.in_(["finished", "pending", "incomplete"]),
                    self.SQLQuestState.timestamp_end < answers_entry.timestamp_end,
                )
            ).order_by(self.SQLQuestState.timestamp_end.desc()).limit(previous).all()
        #tell wcs you send all answers not only the new
            return answers_entry, previous_answers_entries
        else:
            return answers_entry


    def _sentiment_query(
        self, session: "Session", sender_id: Text) -> "Query":
        """Provide the query to retrieve the sender message and their sentiment for a specific sender.
           The messages were the result of free-text questions about the user's mood or a general question asking where the user
           wants to report anything of any nature.

        Args:
            session: Current database session.
            sender_id: Sender id whose conversation events should be retrieved.

        Returns:
            Returns the following objects with max 2 items each. The two objects should have the same length.
            - Dictionary in the form {"message": Query result of the first user message,contains sentiment data, 
                                    "slot": [Query result of the second user message, Query result of the sentiment of the second message]
            - A list with whether the messages in the dictionary whould be included in the user's report
              potential list elements "deny", "affirm", "cancel"
        """
        # Subquery to find the timestamp of the latest `SessionStarted` event
        # session_start_sub_query = (
        #     session.query(sa.func.max(self.SQLEvent.timestamp).label("session_start"))
        #     .filter(
        #         self.SQLEvent.sender_id == sender_id,
        #         self.SQLEvent.type_name == SessionStarted.type_name,
        #     )
        #     .subquery()
        # )

        session_start_timestamp = session.query(sa.func.max(self.SQLEvent.timestamp)).filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.type_name == SessionStarted.type_name,
            ).first()[0]
       

        #get first message, question: How are you?
        message_entry = session.query(self.SQLEvent).filter(
            self.SQLEvent.sender_id == sender_id,
            self.SQLEvent.type_name == "user",
            self.SQLEvent.intent_name == "inform",
            self.SQLEvent.timestamp >= session_start_timestamp,
        ).order_by(self.SQLEvent.timestamp).first()

        # if there is no second message, it means the first message had positive or neutral sentiment
        # and is not included in the report
        try: 
            include_in_report_intent = session.query(self.SQLEvent.intent_name).filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.type_name == "user",
                self.SQLEvent.intent_name.in_(["deny", "affirm", "cancel"]),
                self.SQLEvent.timestamp >= message_entry.timestamp,
                ).order_by(self.SQLEvent.timestamp).first()[0]
        except:
            include_in_report_intent = "deny"

        # get second message, question: Is there anything else you would like ot report..?
        message_entry2 = session.query(self.SQLEvent).filter(
            self.SQLEvent.sender_id == sender_id,
            self.SQLEvent.type_name == "slot",
            self.SQLEvent.action_name == "report_extra_Q1",
            self.SQLEvent.timestamp >= message_entry.timestamp,
        ).order_by(self.SQLEvent.timestamp).first()


        if message_entry2:
            # get the sentiment of the second message seperatly because the message is stored in a slot and does not included it
            # sort in descending order to get the correct sentiment_classes slot
            sentiment2 = session.query(self.SQLEvent).filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.type_name == "slot",
                self.SQLEvent.action_name == "sentiment_classes",
                self.SQLEvent.timestamp.between(message_entry.timestamp, message_entry2.timestamp),
                ).order_by(self.SQLEvent.timestamp.desc()).first()

            message_entries = {"message": message_entry, "slot": [message_entry2, sentiment2]}
            report = [include_in_report_intent, "affirm"]
        else:
            message_entries = {"message": message_entry}
            report = [include_in_report_intent]

        return message_entries, report

    def _first_time_of_day_query(
        self, session: "Session", sender_id: Text) -> "Query":
        """Query to retrieve whether is the first time of day the user was greeted by the agent (i.e. talked to the agent)

        Args:
            session: Current database session.
            sender_id: Sender id whose conversation events should be retrieved.

        Returns:
            Boolean, True=first time, False=not first time
        """
        today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        return session.query(sa.func.min(self.SQLEvent.timestamp)).filter(
            self.SQLEvent.sender_id == sender_id,
            self.SQLEvent.type_name == "action",
            self.SQLEvent.action_name == "action_utter_how_are_you",
            self.SQLEvent.timestamp >= today,
        ).first()[0] is None


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
                # temp_data = json.dumps(data)
                # if "sentiment_classes" in temp_data:
                #     data["in_dashboard"] = "true" 
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
            if q_events:
                question_events = [json.loads(event.data) for event in q_events]
                slot_events = [json.loads(event.data) for event in s_events]
                #answers_data = UniqueDict()
                answers_data = []

                for i, (question_data, slot_data) in enumerate(zip(question_events, slot_events)):
                    print(question_data, slot_data)
                    if i==0:
                        init_timestamp = slot_data.get("timestamp")
                    timestamp = slot_data.get("timestamp")

                    try:
                        question_number = slot_data.get("name").split("Q")[1]
                    except:
                        question_number = slot_data.get("name").split(questionnaire_name + "_")[1]
                
                    # example: {"number": "1", "question": "How difficult is it..?", "answer": "very", "timestamp": ""}
                    answers_data.append({"number": question_number, "question": question_data.get("text"), "answer": slot_data.get("value"), "timestamp": datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%dT%H:%M:%SZ")})

                print(answers_data)
                try:
                    database_entry = self._questionnaire_state_query(session, sender_id, init_timestamp, questionnaire_name).first()
                    if database_entry.state=="available":
                        database_entry.timestamp_start=init_timestamp
                        database_entry.answers = json.dumps(answers_data)
                    elif database_entry.state=="pending":
                        previous_answers = json.loads(database_entry.answers)
                        answers_data.extend(previous_answers)
                        database_entry.answers = json.dumps(answers_data)#json.dumps({key: value for (key, value) in answers_data.items()})
                    if isFinished:
                        database_entry.timestamp_end=timestamp
                        database_entry.state="finished"
                        # create new row in database
                        
                        #TODO: uncomment for schedule
                        #doing this everyday for the msdomain_daily might not be so efficient
                        #new_timestamp = getNextQuestTimestamp(schedule_df, questionnaire_name, datetime.datetime.fromtimestamp(database_entry.available_at))

                        #TODO: uncomment for schedule (1 line)                 
                        new_timestamp = (datetime.datetime.fromtimestamp(database_entry.available_at)+datetime.timedelta(days=3)).timestamp()
                    
                        session.add(
                            self.SQLQuestState(
                            sender_id=sender_id,
                            questionnaire_name=questionnaire_name,
                            available_at=new_timestamp,
                            state="available",
                            timestamp_start=None,
                            timestamp_end=None,
                            answers=None,                          
                            )
                        )

                        # previous version where we keep the same database entry and change the available_at timestamp
                        # new_day = (datetime.datetime.fromtimestamp(database_entry.available_at)+datetime.timedelta(days=3)).timestamp()
                        # database_entry.available_at= new_day
                        # database_entry.state="available"
                        # database_entry.timestamp_start=None
                        # database_entry.timestamp_end=None # this seems to not be used
                        # database_entry.answers = None
                    else:
                        database_entry.state="pending"
                        database_entry.timestamp_end=timestamp
                except:
                    print("Error: no such entry in database table 'questionnaires_state'.")

            session.commit()

        logger.debug(f"Questionnaire answers with sender_id '{tracker.sender_id}' stored to database")

    def getSpecificQuestionnaireAvailability(self, sender_id, current_datetime, questionnaire_name) -> bool:
        current_timestamp = current_datetime.timestamp()
        with self.session_scope() as session:
            isAvailable = self._questionnaire_state_query(session, sender_id, current_timestamp, questionnaire_name).first() is not None
        return isAvailable

    def isFirstTimeToday(self, sender_id) -> bool:
        with self.session_scope() as session:
            isFirstTime = self._first_time_of_day_query(session, sender_id) 
        return isFirstTime

    def getAvailableQuestionnaires(self, sender_id, current_datetime) -> List[str]:
        """ Retrieve current available questionnaires"""
        available_questionnaires, reset_questionnaires = [],[]
        current_timestamp = current_datetime.timestamp()
        with self.session_scope() as session:
            database_entries = self._questionnaire_state_query(session, sender_id, current_timestamp).all()
            for entry in database_entries:
                # this step might need to happen somewhere else, myb automatically
                # checks whether 1 day has passed after the questionnaire was first available
                time_limit = (datetime.datetime.fromtimestamp(entry.available_at)+datetime.timedelta(days=1)).timestamp()

                if time_limit < current_datetime.timestamp():
                    entry.state = "incomplete"

                    # create new database entry
                    new_timestamp = (datetime.datetime.fromtimestamp(entry.available_at)+datetime.timedelta(days=3)).timestamp()

                    session.add(
                        self.SQLQuestState(
                        sender_id=sender_id,
                        questionnaire_name=entry.questionnaire_name,
                        available_at=new_timestamp,
                        state="available",
                        timestamp_start=None,
                        timestamp_end=None,
                        answers=None,                          
                        )
                    )

                    # previous version where we keep the same database entry and change the available_at timestamp
                    # new_day = (datetime.datetime.fromtimestamp(entry.available_at)+datetime.timedelta(days=3)).timestamp()
                    # entry.available_at= new_day
                    # entry.state="available"
                    # entry.timestamp_start=None
                    # entry.timestamp_end=None
                    # entry.answers = None

                    # questionnaires that are passed the time limit need to be reset
                    #reset_questionnaires.append(entry.questionnaire_name)
                else:
                    # when the questionnaire becomes available again, reset its slots 
                    if entry.state == "available":
                        reset_questionnaires.append(entry.questionnaire_name)
                    available_questionnaires.append(entry.questionnaire_name)
            session.commit()
        return available_questionnaires, reset_questionnaires 

    # new version with scheduling
    # def getAvailableQuestionnaires(self, sender_id, current_datetime) -> List[str]:
    #     """ Retrieve current available questionnaires"""
    #     available_questionnaires, reset_questionnaires = [],[]
    #     current_timestamp = current_datetime.timestamp()
    #     with self.session_scope() as session:
    #         database_entries = self._questionnaire_state_query(session, sender_id, current_timestamp).all()
    #         for entry in database_entries:
    #             # this step might need to happen somewhere else, myb automatically
    #             # checks whether 1 or 2 days has passed after the questionnaire was first available
    #             df_row = schedule_df.loc[schedule_df["questionnaire_abvr"] == entry.questionnaire_name]
    #             lifespanInDays = df_row["lifespanInDays"]
    #             time_limit = (datetime.datetime.fromtimestamp(entry.available_at)+datetime.timedelta(days=lifespanInDays)).timestamp()
                
    #             if time_limit < current_datetime.timestamp():
    #                 entry.state = "incomplete"

    #                 # create new database entry
    #                 # doing this everyday for the msdomain_daily might not be so efficient
    #                 new_timestamp = getNextQuestTimestamp(schedule_df, entry.questionnaire_name, datetime.datetime.fromtimestamp(entry.available_at))
                
    #                 session.add(
    #                     self.SQLQuestState(
    #                     sender_id=sender_id,
    #                     questionnaire_name=entry.questionnaire_name,
    #                     available_at=new_timestamp,
    #                     state="available",
    #                     timestamp_start=None,
    #                     timestamp_end=None,
    #                     answers=None,                          
    #                     )
    #                 )

    #                 # previous version where we keep the same database entry and change the available_at timestamp
    #                 # new_day = (datetime.datetime.fromtimestamp(entry.available_at)+datetime.timedelta(days=3)).timestamp()
    #                 # entry.available_at= new_day
    #                 # entry.state="available"
    #                 # entry.timestamp_start=None
    #                 # entry.timestamp_end=None
    #                 # entry.answers = None

    #                 # questionnaires that are passed the time limit need to be reset
    #                 reset_questionnaires.append(entry.questionnaire_name)
    #             else:
    #                 available_questionnaires.append(entry.questionnaire_name)
    #         session.commit()
    #     return available_questionnaires, reset_questionnaires 


    def saveToOntology(self, sender_id):
        ontology_data = {"user_id": sender_id, "source": "Conversational Agent", "observations" : []}
        with self.session_scope() as session:
            message_entries, include_in_report_intents = self._sentiment_query(session, sender_id)

            intent_to_bool = {"affirm": True, "deny": False, "cancel": False}

            for (type, message), intent  in zip(message_entries.items(), include_in_report_intents):
                if type == "message":
                    message_data = json.loads(message.data)
                    message_sentiment = message_data.get("parse_data", {}).get("entities", {})[1].get("value") # returns a list of dicts
                    #sentiment = json.loads(message_data.get("parse_data", {}).get("entities", {})[1].get("value")[0])
                    timestamp = datetime.datetime.fromtimestamp(message.timestamp).strftime("%Y-%m-%dT%H:%M:%SZ")
                    message_text = message.message
                elif type == "slot":
                    message_sentiment = json.loads(message[1].data).get("value")
                    timestamp = datetime.datetime.fromtimestamp(message[0].timestamp).strftime("%Y-%m-%dT%H:%M:%SZ")
                    message_text = json.loads(message[0].data).get("value")

                # this change is required to match the ontolody format
                # this might be removed in the future
                temp_sentiment = json.dumps(message_sentiment)
                temp_sentiment = temp_sentiment.replace("positive", "Positive")
                temp_sentiment = temp_sentiment.replace("negative", "Negative")
                temp_sentiment = temp_sentiment.replace("neutral", "Neutral")

                data = {"sentiment_scores": json.loads(temp_sentiment),
                    "timestamp": timestamp,
                    "explanation": message_text,
                    "in_dashboard": intent_to_bool[intent]}
                ontology_data["observations"].append(data)
            
            print(ontology_data)
        #TODO:send to ontology
        #response = requests.post("ONTOLOGY_CA_ENDPOINT", json=ontology_data)
        #print(response)

    def checkUserID(self, sender_id):
        """ Checks if the specific user id is in the database. If not it adds it"""
        with self.session_scope() as session:
            exists = session.query(self.SQLUserID).filter(self.SQLUserID.sender_id == sender_id).first() is not None
            if not exists:
                #temp
                usecase = sender_id[:len(sender_id)-2].upper()
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
                now = now.replace(hour=0, minute=0, second=0, microsecond=0)
                for questionnaire in questionnaire_per_usecase[usecase]:
                    #timestamp = (now + datetime.timedelta(days=1)).timestamp()
                    timestamp = now.timestamp()
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

    def checkUserIDnew(self, sender_id):
        """ Checks if the specific user id is in the database. 
            If not
            - adds the user id and his/her onboarding date on the information provided by WCS
            - adds the first set of questionnaires"""
        with self.session_scope() as session:
            exists = session.query(self.SQLUserID).filter(self.SQLUserID.sender_id == sender_id).first() is not None
            if not exists:
                response = requests.get("WCS_ONBOARDING_ENDPOINT", json={"patient_uuid": sender_id})
                # need to check this
                resp = response.json() 
                if resp["partner"] == "FISM":
                  usecase = "MS"
                elif resp["partner"] == "SUUB":
                  usecase = "STROKE"
                else:
                   usecase = "PD"
                if usecase not in questionnaire_per_usecase.keys():
                    return
                registration_date = resp["registration_date"]
                registration_timestamp = datetime.datetime.strptime(registration_date, "%Y-%m-%d").timestamp()
                # usecase = sender_id[:len(sender_id)-2].upper()
                # if usecase not in questionnaire_per_usecase.keys():
                #     return
                # now = datetime.datetime.today() 
                session.add(
                    self.SQLUserID(
                        sender_id=sender_id,
                        usecase=usecase,
                        onboarding_timestamp=registration_timestamp,
                        #timezone=timezone,                        
                    )
                )

                df_questionnaires=schedule_df[schedule_df["usecase"]==usecase]
                #onboarding_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                
                for questionnaire in df_questionnaires["questionnaire_abvr"]: 
                    first_monday = registration_date + datetime.timedelta(days=(0-registration_date.weekday())%7)
                    #doing this everyday for the msdomain_dialy might not be so efficient
                    timestamp = getFirstQuestTimestamp(schedule_df, questionnaire, first_monday)
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

    def sendQuestionnareStatus(self, sender_id, questionnare_abvr, status):
        """ Sends the status of the questionnaire to WCS

        Object should be of the format:
        {
            "patient_uuid": "uuid",
            "abbreviation": "String",
            "status": "enum",
            "submission_date": "yyyy-MM-dd",
            "questionnaire_answers": [{
                    "number": "String",
                    "question": "String",
                    "answer": "String"
            }]
        }

        Available Status: COMPLETED, IN_PROGRESS, CANCELED
        """

        submission_date = datetime.date.today()
        questionnaire_data = {"patient_uuid": sender_id, 
                        "abbreviation": questionnare_abvr, 
                        "status": status, 
                        "submission_date" : submission_date.strftime("%Y-%m-%d")}
    
        # msdomainIV check again
        if questionnare_abvr in ["MSdomainIV_Daily", "STROKEdomainIV"]:            
            with self.session_scope() as session:
                answers_events  = self._questionnaire_answers_query(session, sender_id, questionnare_abvr)
                answers = json.loads(answers_events.answers)
                # remove the timestamp of each message
                res_answers = [{key : val for key, val in d.items() if key != "timestamp"} for d in answers]
                session.commit()    
            questionnaire_data["questionnaire_answers"] = res_answers
        elif questionnare_abvr == "dizzNbalance":
            new_symptoms = self.getDizzinessNbalanceNewSymptoms(sender_id)
            areNewSymptoms = str(len(new_symptoms) > 0)
            questionnaire_data["questionnaire_answers"] =[{
                    "number": "Symptoms",
                    "question": "SYMPTOMS: Select all that apply and press send:",
                    "answer": areNewSymptoms}]

        #TODO:send to wcs
        print(questionnaire_data)
        #response = requests.post("WCS_STATUS_ENDPOINT", json=questionnaire_data)
        #print(response)

    def getDizzinessNbalanceNewSymptoms(self, sender_id):
        """ Gets the symptoms of the latest Dizziness and Balance questionnaire and of the one before that
            Compares the symptoms and sends all new symptoms to wcs for the alert mechanism"""
        with self.session_scope() as session:
            answers_events, previous_answers_events  = self._questionnaire_answers_query(session, sender_id, "dizzNbalance", False, 1)
            answers = json.loads(answers_events.answers)
            new_symptoms = []
            if previous_answers_events:
                previous_answers = json.loads(previous_answers_events[0].answers)   
                symptoms= [answer["answers"] for answer in answers if answer["number"] == "Symptoms"]
                previous_symptoms= [answer["answers"] for answer in previous_answers if answer["number"] == "Symptoms"]
                # do this because anwers are in the form ["symptom1, symptom2"]
                symptoms = symptoms[0].split(", ")
                previous_symptoms = previous_symptoms[0].split(", ")
                new_symptoms = [x for x in symptoms if x not in previous_symptoms]
            session.commit()
            return new_symptoms   

def getFirstQuestTimestamp(schedule_df, questionnaire_name, init_date):
    """Get the date the specified questionnaire will be available for the first time
    Args: 
        schedule_df: pandas dataframe containing the schedule
        questionnaire_name:
        init_date: initial date in datetime format
    Returns:
        timestamp"""
    df_row=schedule_df.loc[schedule_df["questionnaire_abvr"] == questionnaire_name]                    
    dayOfWeek=int(df_row["dayOfWeek"].values[0])
    weekOfMonth=int(df_row["weekOfMonth"].values[0])
    frequencyInWeeks=int(df_row["frequencyInWeeks"].values[0])
    # if the questionnaire is not available in the current month 
    if frequencyInWeeks > 4:
        weekOfMonth = frequencyInWeeks-1

    if questionnaire_name == "MSdomainIV_Daily":
        q_day = getNextKTimestamps(init_date,1)[0]
    else:
        q_day = (init_date + datetime.timedelta(days=dayOfWeek, weeks=max(0,weekOfMonth-1))).timestamp()
    return q_day



def getNextQuestTimestamp(schedule_df, questionnaire_name, init_date):
    """Get the next date the specified questionnaire will be available given an intial date
    Args: 
        schedule_df: pandas dataframe containing the schedule
        questionnaire_name:
        init_date: initial date in datetime format
    Returns:
        timestamp"""
    df_row = schedule_df.loc[schedule_df["questionnaire_abvr"] == questionnaire_name]                    
    frequencyInWeeks=int(df_row["frequencyInWeeks"].values[0])

    if questionnaire_name == "MSdomainIV_Daily":
        q_day = getNextKTimestamps(init_date,1)[0]
    else:
        q_day = (init_date + datetime.timedelta(weeks=frequencyInWeeks)).timestamp()
    return q_day



def getNextKTimestamps(init_date, number_of_days:int=7):
    """Get the next (number_of_days) timestamps after an intial date
    Args: 
        init_date: initial date in datetime format
        number_of_days: number of next days
    Returns:
        timestamp"""    
    q_days = []
    for i in range(number_of_days):
        q_days.append((init_date + datetime.timedelta(days=i+1)).timestamp())
    return q_days                    

if __name__ == "__main__":
    ts = CustomSQLTrackerStore(db="demo.db")
    #print(ts.getAvailableQuestionnaires("stroke00",datetime.datetime.now()))
    #print(ts.saveQuestionnaireAnswers("stroke03", "activLim", False))
    now = datetime.datetime.today()
    first_monday = now + datetime.timedelta(days=(0-now.weekday())%7)
    q_day = first_monday + datetime.timedelta(days=5, weeks=max(0,4-1))
    #print(q_day)

    #print(1654808400<now)
    with ts.session_scope() as session:
        #question_events = ts._questionnaire_state_query(session, "stroke05", now, "activLim")
        #print(question_events.first().state)
        #q = [json.loads(event.data) for event in question_events]
        #print(q)
        question_events, slot = ts._questionnaire_query(session, "ms11", "MSdomainII_3M")
        # print([json.loads(event.data) for event in question_events])
        # print([json.loads(event.data) for event in slot])
        #print(ts._first_time_of_day_query(session, "stroke23"))

        #answers, previous_answers = ts._questionnaire_state_query(session, "stroke04", now, "activLim")
        #print(previous_answers)

        #ts.saveToOntology("ms24")
        ts._sentiment_query(session, "ms28")
        #ts.sendQuestionnareStatus("stroke01", "dizzNbalance", "COMPLETED")
        #ts.getDizzinessNbalanceNewSymptoms("stroke01")


  


