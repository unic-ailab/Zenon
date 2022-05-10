from __future__ import annotations
import contextlib
from http.client import ImproperConnectionState
import itertools
import json
import logging
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
        """Represents an event in the SQL Tracker Store."""

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
        self, session: "Session", sender_id: Text, questionnaire_name: Text
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
        # latest_questionnaire_sub_query = (
        #     session.query(sa.func.max(self.SQLQuestState.timestamp).label(questionnaire_name))
        #     .filter(
        #         self.SQLEvent.sender_id == sender_id,
        #     )
        #     .subquery()
        # )

        # different time per pilot or save in specific timezone

        latest_questionnaire_sub_sub_query = (
            session.query(sa.func.max(self.SQLEvent.timestamp).label("questionnaire_start"))
            .filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.intent_name == questionnaire_name+"_start",
            )
            .subquery()
        )

        event_sub_query = (
            session.query(self.SQLEvent)
            .filter(
                # Find events after the latest `questionnaire_started` event
                    self.SQLEvent.sender_id == sender_id,
                    self.SQLEvent.timestamp > latest_questionnaire_sub_sub_query.c.questionnaire_start,
                )
            )
            
                

        question_events = event_sub_query.filter(
            self.SQLEvent.type_name == "bot"
        )

        # this needs a lot of testing, it might not work for all cases
        slot_events_1 = event_sub_query.filter(
            sa.and_(
                    self.SQLEvent.type_name == "slot",
                    self.SQLEvent.action_name != "sentiment",
                )
        )

        slot_events_2 = event_sub_query.filter(
            sa.and_(
                    self.SQLEvent.type_name == "user",
                    self.SQLEvent.intent_name == "out_of_scope",
                )
        )

        return question_events, slot_events_1.union(slot_events_2).all()

    def _questionnaire_state_query(
        self, session: "Session", sender_id: Text, questionnaire_name: Text, timestamp: float):
        """Provide the query to retrieve the conversation events for a specific sender.

        Args:
            session: Current database session.
            sender_id: Sender id whose conversation events should be retrieved.
            fetch_events_from_all_sessions: Whether to fetch events from all
                conversation sessions. If `False`, only fetch events from the
                latest conversation session.

        Returns:
            One database row entry.
        """

        available_questionnaire_sub_query = session.query(self.SQLQuestState.state).filter(
            sa.or_(
                self.SQLQuestState.state == "available",
                self.SQLQuestState.state == "pending",
            )).subquery()

        database_entry = (
            session.query(self.SQLQuestState)
            .filter(
                self.SQLQuestState.sender_id == sender_id,
                self.SQLQuestState.questionnaire_name == questionnaire_name,
                self.SQLQuestState.state.in_(available_questionnaire_sub_query),
                self.SQLQuestState.available_at >= timestamp,
            )
        ).first()
        

        return database_entry


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
        """Update database with answers from the relevant questions."""

        if self.event_broker:
            self.stream_events(tracker)

        with self.session_scope() as session:
            question_events, slot_events  = self._questionnaire_query(session, sender_id, domain_name)
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
        """Update database with events from the current conversation."""

        class UniqueDict(dict):
            def __setitem__(self, key, value):
                if key not in self:
                    dict.__setitem__(self, key, value)
                else:
                    raise print("Key already exists")

        if self.event_broker:
            self.stream_events(tracker)

        with self.session_scope() as session:
            question_events, slot_events  = self._questionnaire_query(session, sender_id, questionnaire_name)
            question_events = [json.loads(event.data) for event in question_events]
            slot_events = [json.loads(event.data) for event in slot_events]

            answers_data = UniqueDict()

            for i, (question_data, slot_data) in enumerate(zip(question_events, slot_events)):
                if i==0:
                    init_timestamp = slot_data.get("timestamp")
                timestamp = slot_data.get("timestamp")

                # example: {q1: {"question": "How difficult is it..?", "answer": "very", "timestamp": }}
                answers_data[slot_data.get("name")] = {"question": question_data.get("text"), "answer": slot_data.get("value"), "timestamp": timestamp}


            database_entry = self._questionnaire_state_query(session, sender_id, questionnaire_name, init_timestamp)
            try:
                if database_entry.state=="available":
                    database_entry.timestamp_start=init_timestamp
                    database_entry.answers = json.dumps(answers_data)
                else:
                    previous_answers = json.loads(database_entry.answers)
                    database_entry.answers = json.dumps({key: value for (key, value) in (previous_answers.items() + answers_data.items())})

                if isFinished:
                    database_entry.timestamp_end=timestamp
                    database_entry.state="finished"
                else:
                    database_entry.state="pending"
            except:
                print("Error: no such entry in database table 'questionnaires_state'.")

            session.commit()

        logger.debug(f"Questionnaire answers with sender_id '{tracker.sender_id}' stored to database")
