from __future__ import annotations
from ast import Continue
import contextlib
from http.client import ImproperConnectionState
import itertools
import json
import logging
import datetime
import requests
import pandas as pd
import pytz
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
    Tuple,
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

from rasa.core.tracker_store import (
    TrackerStore,
    _create_sequence,
    create_engine_kwargs,
    ensure_schema_exists,
)

from connect_to_iam import BearerAuth, VerifyAuthentication

logging.basicConfig(
    filename="zenon.log",
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# will relevant questions be available from the chatbot outside notifications?
questionnaire_per_usecase = {
    "MS": [
        "MSdomainI",
        "MSdomainII_1M",
        "MSdomainII_3M",
        "MSdomainIII_1W",
        "MSdomainIII_2W",
        "MSdomainIV_Daily",
        "MSdomainIV_1W",
        "MSdomainV",
    ],
    "STROKE": [
        "activLim",
        "muscletone",
        "dizzNbalance",
        "eatinghabits",
        "psqi",
        "coast",
        "STROKEdomainIII",
        "STROKEdomainIV",
        "STROKEdomainV",
    ],
}

questionnaire_names_list = [
    "MSdomainI",
    "MSdomainII_1M",
    "MSdomainII_3M",
    "MSdomainIII_1W",
    "MSdomainIII_2W",
    "MSdomainIV_Daily",
    "MSdomainIV_1W",
    "MSdomainV",
    "activLim",
    "muscletone",
    "dizzNbalance",
    "eatinghabits",
    "psqi",
    "coast",
    "STROKEdomainIII",
    "STROKEdomainIV",
    "STROKEdomainV",
]

schedule_df = pd.read_csv("pilot_schedule.csv")
endpoints_df = pd.read_csv("alameda_endpoints.csv")
testers_ids_df = pd.read_csv("testers_ids.csv")


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
        # sentiment = sa.Column(sa.Text)
        type_name = sa.Column(sa.String(255), nullable=False)
        timestamp = sa.Column(sa.Float)
        intent_name = sa.Column(sa.String(255))
        action_name = sa.Column(sa.String(255))
        data = sa.Column(sa.Text)

        def __repr__(self):
            """Add representation to print queries in human readable way"""

            return f"SQLEvent(\nsender_id={self.sender_id},\nmessage={self.message}\nintent={self.intent_name}\data={self.data})"

    class SQLQuestState(Base):
        """Represents a questionnaire event in the SQL Tracker Store.
        Available options for "state":
         - available: the questionnaire is available to answer
         - pending: some of the questions have been answered and the questionnaire is available
         - incomplete: the questionnaire has not been completed and is no longer available
         - finished: the questiionnaire was completed
         - to_be_stored: the questionnaire's answers are about to be stored (temp state, used until the database catches up with the dialogue)
        """

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
        scoring = sa.Column(sa.Text)

        def __repr__(self):
            """Add representation to print queries in human readable way"""

            return f"SQLQuestState(\nsender_id={self.sender_id}\nquestionnaire_name={self.questionnaire_name}\nstate= {self.state}\navailable_at={self.available_at})"

    class SQLUserID(Base):
        """Represents a user id event in the SQL Tracker Store."""

        __tablename__ = "userIDs"
        # `create_sequence` is needed to create a sequence for databases that
        # don't autoincrement Integer primary keys (e.g. Oracle)
        id = sa.Column(sa.Integer, _create_sequence(__tablename__), primary_key=True)
        sender_id = sa.Column(sa.String(255), nullable=False, index=True)
        usecase = sa.Column(sa.String(255), nullable=False)
        onboarding_timestamp = sa.Column(sa.Float)
        language = sa.Column(sa.String(255))
        timezone = sa.Column(sa.String(255))

    class SQLIssue(Base):
        """Represents an event in the SQL Tracker Store."""

        __tablename__ = "issues"
        id = sa.Column(sa.Integer, _create_sequence(__tablename__), primary_key=True)
        sender_id = sa.Column(sa.String(255), nullable=False, index=True)
        timestamp = sa.Column(sa.Float)
        description = sa.Column(sa.String(255))

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

        return sa.engine.url.URL.create(
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
        # Remove this in Rasa Open Source 3.0 along with the
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
        # Subquery to find the timestamp of the latest `session_started` event
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
                # Find events after the latest `session_started` event or return all
                # events
                sa.or_(
                    self.SQLEvent.timestamp >= session_start_sub_query.c.session_start,
                    session_start_sub_query.c.session_start.is_(None),
                )
            )

        return event_query.order_by(self.SQLEvent.timestamp)

    def _questionnaire_query(
        self,
        session: "Session",
        sender_id: Text,
        questionnaire_name: Text,
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

        if questionnaire_name in ["MSdomainIII_2W", "MSdomainII_3M"]:
            # Subquery to find the timestamp of the latest `Questionnaire_Start` event
            latest_questionnaire_sub_query = (
                session.query(
                    sa.func.max(self.SQLEvent.timestamp).label("questionnaire_start")
                )
                .filter(
                    self.SQLEvent.sender_id == sender_id,
                    self.SQLEvent.action_name == "action_questionnaire_completed",
                    self.SQLEvent.type_name == "action",
                    # self.SQLEvent.timestamp >= timestamp,
                )
                .subquery()
            )
        else:
            latest_questionnaire_sub_query = (
                session.query(
                    sa.func.max(self.SQLEvent.timestamp).label("questionnaire_start")
                )
                .filter(
                    self.SQLEvent.sender_id == sender_id,
                    self.SQLEvent.intent_name == questionnaire_name + "_start",
                    self.SQLEvent.type_name == "user",
                    # self.SQLEvent.timestamp >= timestamp,
                )
                .subquery()
            )

        # this returns a tuple in the form (1655132361.3270664,)
        latest_start_time = (
            session.query(sa.func.min(self.SQLEvent.timestamp))
            .filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.action_name.ilike("requested_slot"),
                self.SQLEvent.type_name == "slot",
                self.SQLEvent.timestamp
                > latest_questionnaire_sub_query.c.questionnaire_start,
            )
            .first()[0]
        )

        cancel_request_timestamp = (
            session.query(sa.func.min(self.SQLEvent.timestamp))
            .filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.intent_name == "cancel",
                self.SQLEvent.type_name == "user",
                self.SQLEvent.timestamp >= latest_start_time,
            )
            .first()[0]
        )

        if cancel_request_timestamp is not None:
            latest_end_time = cancel_request_timestamp
        else:
            latest_end_time = (
                session.query(sa.func.max(self.SQLEvent.timestamp))
                .filter(
                    self.SQLEvent.sender_id == sender_id,
                    self.SQLEvent.type_name == "slot",
                    self.SQLEvent.action_name.ilike(questionnaire_name + "_%"),
                    self.SQLEvent.timestamp > latest_start_time,
                )
                .first()[0]
            )

        question_events = (
            session.query(self.SQLEvent)
            .filter(
                self.SQLEvent.sender_id == sender_id,
                # self.SQLEvent.timestamp >= latest_questionnaire_sub_query.c.questionnaire_start,
                # self.SQLEvent.timestamp.between(latest_start_time, latest_end_time),
                self.SQLEvent.timestamp >= latest_start_time,
                self.SQLEvent.timestamp < latest_end_time,
                self.SQLEvent.type_name == "bot",
            )
            .order_by(self.SQLEvent.timestamp)
            .all()
        )

        slot_events = (
            session.query(self.SQLEvent)
            .filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.type_name == "slot",
                self.SQLEvent.timestamp.between(latest_start_time, latest_end_time),
                self.SQLEvent.action_name.notlike(questionnaire_name + "_%_score"),
                self.SQLEvent.action_name.notlike(questionnaire_name + "_score"),
                self.SQLEvent.action_name.ilike(questionnaire_name + "_%"),
            )
            .order_by(self.SQLEvent.timestamp)
            .all()
        )

        return question_events, slot_events

    def _questionnaire_state_query(
        self,
        session: "Session",
        sender_id: Text,
        timestamp: float,
        questionnaire_name: Text = None,
    ):
        """Provide the query to retrieve the questionnaire state events for a specific sender.

        Args:
            session: Current database session.
            sender_id: Sender id whose conversation events should be retrieved.
            questionnaire_name: The name of the questionnaire whose questions and responses should be retrieved.


        Returns:
            One database row entry.
        """

        if questionnaire_name:
            database_entries = (
                session.query(self.SQLQuestState).filter(
                    self.SQLQuestState.sender_id == sender_id,
                    self.SQLQuestState.questionnaire_name == questionnaire_name,
                    self.SQLQuestState.state.in_(
                        ["available", "pending", "to_be_stored"]
                    ),
                    self.SQLQuestState.available_at <= timestamp,
                )
            ).order_by(self.SQLQuestState.available_at)
        else:
            database_entries = (
                session.query(self.SQLQuestState).filter(
                    self.SQLQuestState.sender_id == sender_id,
                    self.SQLQuestState.state.in_(
                        ["available", "pending", "to_be_stored"]
                    ),
                    self.SQLQuestState.available_at <= timestamp,
                )
            ).order_by(self.SQLQuestState.available_at)

        return database_entries

    def _questionnaire_answers_query(
        self,
        session: "Session",
        sender_id: Text,
        questionnaire_name: Text,
        onlyFinished: bool = False,
        previous: int = 0,
    ):
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

        latest_questionnaire_sub_query = (
            session.query(
                sa.func.max(self.SQLQuestState.timestamp_end).label("latest_timestamp")
            )
            .filter(
                sa.and_(
                    self.SQLQuestState.sender_id == sender_id,
                    self.SQLQuestState.questionnaire_name == questionnaire_name,
                    self.SQLQuestState.state.in_(states),
                )
            )
            .subquery()
        )

        answers_entry = (
            session.query(self.SQLQuestState).filter(
                self.SQLQuestState.sender_id == sender_id,
                self.SQLQuestState.questionnaire_name == questionnaire_name,
                self.SQLQuestState.state.in_(states),
                self.SQLQuestState.timestamp_end
                >= latest_questionnaire_sub_query.c.latest_timestamp,
            )
        ).first()
        if previous > 0:
            previous_answers_entries = (
                (
                    session.query(self.SQLQuestState.answers).filter(
                        self.SQLQuestState.sender_id == sender_id,
                        self.SQLQuestState.questionnaire_name == questionnaire_name,
                        self.SQLQuestState.state.in_(
                            ["finished", "pending", "incomplete"]
                        ),
                        self.SQLQuestState.timestamp_end < answers_entry.timestamp_end,
                    )
                )
                .order_by(self.SQLQuestState.timestamp_end.desc())
                .limit(previous)
                .all()
            )
            # tell wcs you send all answers not only the new
            return answers_entry, previous_answers_entries
        else:
            return answers_entry

    def _questionnaire_score_query(
        self,
        session: "Session",
        sender_id: Text,
        questionnaire_name: Text,
    ) -> "Query":
        """Provide the query to retrieve the questionnaire score for a specific sender.

        Args:
            session: Current database session.
            sender_id: Sender id whose conversation events should be retrieved.
            questionnaire_name: The name of the questionnaire.

        Returns:
            Float with questionnaire score.
        """
        latest_questionnaire_score_sub = (
            session.query(
                sa.func.max(self.SQLEvent.timestamp).label("latest_timestamp")
            )
            .filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.action_name.ilike(questionnaire_name + "_score"),
                self.SQLEvent.type_name == "slot",
            )
            .subquery()
        )
        latest_questionnaire_score = (
            session.query(self.SQLEvent.data)
            .filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.action_name.ilike(questionnaire_name + "_score"),
                self.SQLEvent.type_name == "slot",
                self.SQLEvent.timestamp
                >= latest_questionnaire_score_sub.c.latest_timestamp,
            )
            .first()[0]
        )

        data = json.loads(latest_questionnaire_score)
        return float(data.get("value", -1))

    def _questionnaire_name_query(
        self,
        session: "Session",
        sender_id: Text,
        action_name: Text,
    ) -> "Query":
        """Provide the query to retrieve the questionnaire name (abbreviation) after it has been completed or cancelled for a specific sender.

        Args:
            session: Current database session.
            sender_id: Sender id whose conversation events should be retrieved.
            action_name: The name of the action before which the questionnaire name should be retrieved.

        Returns:
            String with questionnaire name.
        """
        latest_timestamp_sub_query = (
            session.query(
                sa.func.max(self.SQLEvent.timestamp).label("latest_timestamp")
            )
            .filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.action_name == action_name,
                self.SQLEvent.type_name == "action",
            )
            .subquery()
        )

        latest_questionnaire_name = (
            (
                session.query(self.SQLEvent.action_name).filter(
                    self.SQLEvent.sender_id == sender_id,
                    self.SQLEvent.action_name.ilike("%_form"),
                    self.SQLEvent.type_name == "action",
                    self.SQLEvent.timestamp
                    <= latest_timestamp_sub_query.c.latest_timestamp,
                )
            )
            .order_by(self.SQLEvent.timestamp.desc())
            .first()[0]
        )

        return latest_questionnaire_name.replace("_form", "")

    def _sentiment_query(self, session: "Session", sender_id: Text) -> "Query":
        """Provide the query to retrieve the sender message and their sentiment for a specific sender.
           The messages were the result of free-text questions about the user's mood or a general question asking whether the user
           wants to report anything of any nature.

        Args:
            session: Current database session.
            sender_id: Sender id whose conversation events should be retrieved.

        Returns:
            Returns the following objects with max 2 items each. The two objects should have the same length.
            - Dictionary in the form {"message": Query result of the first user message,contains sentiment data,
                                    "slot": [Query result of the second user message, Query result of the sentiment of the second message]
            - A list with whether the messages in the dictionary would be included in the user's report
              potential list elements "deny", "affirm", "cancel"
        """

        session_start_timestamp = (
            session.query(sa.func.max(self.SQLEvent.timestamp))
            .filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.type_name == SessionStarted.type_name,
            )
            .first()[0]
        )

        # get first message, question: How are you?
        message_entry = (
            session.query(self.SQLEvent)
            .filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.type_name == "user",
                self.SQLEvent.intent_name == "inform",
                self.SQLEvent.timestamp >= session_start_timestamp,
            )
            .order_by(self.SQLEvent.timestamp)
            .first()
        )

        # print(f"_sentiment_query --- For userID:{sender_id}\n{message_entry}")

        # if there is no second message, it means the first message had positive or neutral sentiment
        # and is not included in the report
        try:
            include_in_report_intent = (
                session.query(self.SQLEvent.intent_name)
                .filter(
                    self.SQLEvent.sender_id == sender_id,
                    self.SQLEvent.type_name == "user",
                    self.SQLEvent.intent_name.in_(["deny", "affirm", "cancel"]),
                    self.SQLEvent.timestamp > message_entry.timestamp,
                )
                .order_by(self.SQLEvent.timestamp.desc())
                .first()[0]
            )
        except:
            include_in_report_intent = "deny"
        print(
            f"_sentiment_query --- For userID:{sender_id}\ninclude_in_report: {include_in_report_intent}"
        )

        # get second message, question: Is there anything else you would like ot report..?
        if message_entry:
            message_entry2 = (
                session.query(self.SQLEvent)
                .filter(
                    self.SQLEvent.sender_id == sender_id,
                    self.SQLEvent.type_name == "slot",
                    self.SQLEvent.action_name == "report_extra_Q1",
                    self.SQLEvent.timestamp >= message_entry.timestamp,
                )
                .order_by(self.SQLEvent.timestamp)
                .first()
            )

            if message_entry2:
                # get the sentiment of the second message seperatly because the message is stored in a slot and does not included it
                # sort in descending order to get the correct sentiment_classes slot
                sentiment2 = (
                    session.query(self.SQLEvent)
                    .filter(
                        self.SQLEvent.sender_id == sender_id,
                        self.SQLEvent.type_name == "slot",
                        self.SQLEvent.action_name == "sentiment_classes",
                        self.SQLEvent.timestamp.between(
                            message_entry.timestamp, message_entry2.timestamp
                        ),
                    )
                    .order_by(self.SQLEvent.timestamp.desc())
                    .first()
                )

                message_entries = {
                    "message": message_entry,
                    "slot": [message_entry2, sentiment2],
                }
                report = [include_in_report_intent, "affirm"]
            else:
                message_entries = {"message": message_entry}
                report = [include_in_report_intent]
        else:
            message_entries = {"message": message_entry}
            report = [include_in_report_intent]

        return message_entries, report

    def _first_time_of_day_query(self, session: "Session", sender_id: Text) -> "Query":
        """Query to retrieve whether is the first time of day the user was greeted by the agent (i.e. talked to the agent)

        Args:
            session: Current database session.
            sender_id: Sender id whose conversation events should be retrieved.

        Returns:
            Boolean, True=first time, False=not first time
        """
        try:
            timezone = pytz.timezone(self.getUserTimezone(sender_id))
        except:
            timezone = pytz.utc
        today = (
            datetime.datetime.now(tz=timezone)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .timestamp()
        )
        return (
            session.query(sa.func.min(self.SQLEvent.timestamp))
            .filter(
                self.SQLEvent.sender_id == sender_id,
                self.SQLEvent.type_name == "action",
                self.SQLEvent.action_name == "action_utter_how_are_you",
                self.SQLEvent.timestamp >= today,
            )
            .first()[0]
            is None
        )

    def checkIfTestingID(self, sender_id):
        """Checks whether the user id is used for testing purposes
        Currently testing ids are of the form:
            - ms42-ms99
            - stroke42-stroke99
        User ids ms41 and stroke41 are also for testing purposes but are left out in order to be used for testing the ontology
        """
        wcs_ids_list = testers_ids_df["sender_id"].tolist()
        if sender_id[: len(sender_id) - 2].upper() in questionnaire_per_usecase.keys():
            if int(sender_id[-2:]) >= 42:
                return True
        elif sender_id in wcs_ids_list:
            return True
        return False

    def save(self, tracker: DialogueStateTracker) -> None:
        """Update database with events from the current conversation."""

        if self.event_broker:
            self.stream_events(tracker)

        with self.session_scope() as session:
            # only store recent events
            events = self._additional_events(session, tracker)

            for event in events:
                data = event.as_dict()
                # if event.type_name == "action" and event.action_name=="action_listen":
                #    continue

                intent = (
                    data.get("parse_data", {}).get("intent", {}).get(INTENT_NAME_KEY)
                )
                action = data.get("name")
                timestamp = data.get("timestamp")
                message = data.get("text")
                sender_id = tracker.sender_id
                # if event.type_name == "user":
                #     sentiment = {
                #         "value": data.get("parse_data", {}).get("entities", {})[0].get("value", ""),
                #         "confidence": data.get("parse_data", {}).get("entities", {})[0].get("confidence", "")
                #     }
                # else:
                #     sentiment = None
                # temp_data = json.dumps(data)
                # if "sentiment_classes" in temp_data:
                #     data["on_dashboard"] = "true"
                # noinspection PyArgumentList
                session.add(
                    self.SQLEvent(
                        sender_id=sender_id,
                        message=message,
                        # sentiment=json.dumps(sentiment),
                        type_name=event.type_name,
                        timestamp=timestamp,
                        intent_name=intent,
                        action_name=action,
                        data=json.dumps(data),
                    )
                )

                if (
                    event.type_name == "action"
                    and event.action_name == "action_ontology_store_sentiment"
                ):
                    # commit to store the events in the database so they can be found by the query
                    session.commit()
                    if not self.checkIfTestingID(sender_id):
                        self.saveToOntology(tracker, sender_id)
                # elif event.type_name == "action" and event.action_name in ["action_questionnaire_completed", "action_questionnaire_cancelled", "action_questionnaire_cancelled_app"]:
                #     # commit to store the events in the database so they can be found by the query
                #     session.commit()
                #     # get questionnaire name because at that stage the questionnaire slot value might have changed
                #     try:
                #         questionnaire_name = self._questionnaire_name_query(session, sender_id, event.action_name)
                #     except:
                #         questionnaire_name = ""
                # if questionnaire_name in questionnaire_names_list:
                # if event.action_name=="action_questionnaire_cancelled" or  event.action_name=="action_questionnaire_cancelled_app":
                # isSaved, isDemo = self.saveQuestionnaireAnswers(sender_id, questionnaire_name, False, tracker)
                # if isSaved and not isDemo: self.sendQuestionnaireStatus(sender_id, questionnaire_name, "IN_PROGRESS")
                # else:
                # isSaved, isDemo = self.saveQuestionnaireAnswers(sender_id, questionnaire_name, True, tracker)
                # if isSaved and not isDemo: self.sendQuestionnaireStatus(sender_id, questionnaire_name, "COMPLETED")

            session.commit()
        print(f"Tracker with sender_id '{tracker.sender_id}' stored to database")

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

    def saveQuestionnaireAnswers(
        self,
        tracker: DialogueStateTracker,
        domain: Domain,
        questionnaire_abbreviation: str,
        questionnaire_name: str,
        isFinished: bool,
    ) -> List[str]:
        """
        Update database with answers from a specific questionnaire.
        The answers of the questionnaires are retrieved directly from their dedicated slot value.

        Args:
        - tracker (DialogueStateTracker): Rasa tracker object
        - domain (Domain): Rasa domain object
        - questionnaire_abbreviation (str): Abbreviation for the questionnaire being answered
        - questionnaire_name (str): Name of the questionnaire being answered
        - isFinished (bool): Whether the questionnaire has been fully completed or not

        Returns:
        - slots_to_reset (List[str]): List of slots that were reset after storing their values
        """

        question_types_df = pd.read_csv("question_types.csv")
        sender_id = tracker.sender_id
        isDemo = (
            sender_id[: len(sender_id) - 2].upper() in questionnaire_per_usecase.keys()
        )
        answers_data = []
        answers_data_wcs_format = []
        slots_to_reset = []
        init_timestamp = tracker.get_slot("q_starting_time")

        with self.session_scope() as session:
            try:
                database_entry = self.checkQuestionnaireTimelimit(
                    session, sender_id, init_timestamp, questionnaire_abbreviation
                )
            except:
                print(
                    f"In custom_tracker_store 'saveQuestionnaireAnswers': no such entry ({sender_id}, {questionnaire_abbreviation}) in database table 'questionnaires_state'."
                )
                return []

            submission_timestamp = datetime.datetime.now(
                pytz.timezone(self.getUserTimezone(sender_id))
            ).timestamp()

            for slot_name in domain["slots"].keys():
                if questionnaire_abbreviation in slot_name:
                    slots_to_reset.append(slot_name)

            for slot_name in slots_to_reset:
                if questionnaire_abbreviation in ["activLim", "dizzNbalance"]:
                    question_number = slot_name.split(questionnaire_abbreviation + "_")[
                        1
                    ]
                else:
                    try:
                        question_number = slot_name.split("Q")[1]
                    except IndexError:
                        print(f"IndexError for slot {slot_name} - Line 904")

                # store answers without storing the questions
                if "score" not in slot_name:
                    try:
                        question_type = question_types_df.loc[
                            question_types_df["slot_name"] == slot_name, "type"
                        ].values[0]
                        answers_data.append(
                            {
                                "question_id": question_number,
                                "question_type": question_type,
                                "answer": tracker.get_slot(slot_name),
                                "score": None,
                            }
                        )
                        answers_data_wcs_format.append(
                            {
                                "number": question_number,
                                "answer": tracker.get_slot(slot_name),
                            }
                        )
                    except IndexError as error:
                        print(error)
                        print(f"For {slot_name} --- saveQuestionnaireAnswers")

            partner, disease = self.getUserDetails(sender_id)
            if questionnaire_abbreviation in ["psqi", "muscletone"]:
                # total_score = self._questionnaire_score_query(session, sender_id, questionnaire_name)
                total_score = tracker.get_slot(questionnaire_abbreviation + "_score")
            else:
                total_score = None

            questionnaire_data = {
                "user_id": sender_id,
                "source": "CA",
                "survey_title": questionnaire_name,
                "partner": partner,
                "disease": disease,
                "abbreviation": questionnaire_abbreviation,
                "submission_date": datetime.datetime.fromtimestamp(
                    submission_timestamp
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "survey_answers": answers_data,
                "survey_score": [{"score": total_score, "scoreDescription": "TOTAL"}],
            }

            if database_entry.state == "available":
                database_entry.timestamp_start = init_timestamp
            elif database_entry.state == "pending":
                database_entry.answers = None
            database_entry.answers = json.dumps(answers_data_wcs_format)
            if isFinished:
                database_entry.timestamp_end = submission_timestamp
                database_entry.state = "finished"

                # send questionnaire score to ontology
                if questionnaire_abbreviation in [
                    "psqi",
                    "muscletone",
                ] and not self.checkIfTestingID(sender_id):
                    self.sendQuestionnaireScoreToOntology(
                        session,
                        tracker,
                        sender_id,
                        questionnaire_abbreviation,
                        questionnaire_data,
                        total_score,
                    )

                # doing this everyday for the msdomain_daily might not be so efficient
                if isDemo or self.getUserUsecase(sender_id).upper() == "STROKE":
                    new_timestamp = submission_timestamp
                else:
                    tz_timezone = pytz.timezone(self.getUserTimezone(sender_id))
                    last_availability = datetime.datetime.fromtimestamp(
                        database_entry.available_at, tz=tz_timezone
                    )
                    new_timestamp = getNextQuestTimestamp(
                        schedule_df,
                        questionnaire_abbreviation,
                        last_availability,
                        tz_timezone,
                    )

                # create new row in database
                session.add(
                    self.SQLQuestState(
                        sender_id=sender_id,
                        questionnaire_name=questionnaire_abbreviation,
                        available_at=new_timestamp,
                        state="available",
                        timestamp_start=None,
                        timestamp_end=None,
                        answers=None,
                        scoring=total_score,
                    )
                )

            else:
                database_entry.state = "pending"
                database_entry.timestamp_end = submission_timestamp
            session.commit()
            if not isDemo and not isFinished:
                self.sendQuestionnaireStatus(
                    tracker, sender_id, questionnaire_abbreviation, "IN_PROGRESS"
                )
            elif not isDemo and isFinished:
                self.sendQuestionnaireStatus(
                    tracker, sender_id, questionnaire_abbreviation, "COMPLETED"
                )

        print(
            f"Questionnaire answers with sender_id '{tracker.sender_id}' stored to database"
        )
        return slots_to_reset

    def getSpecificQuestionnaireAvailability(
        self, sender_id: str, current_timestamp: int, questionnaire_name: str
    ) -> bool:
        """
        Determines if a specific questionnaire is available for the given sender_id and current_timestamp.

        Args:
            sender_id (str): The unique ID of the sender.
            current_timestamp (int): The current timestamp.
            questionnaire_name (str): The name of the questionnaire to check availability for.

        Returns:
            bool: True if the questionnaire is available, False otherwise.
        """
        with self.session_scope() as session:
            try:
                _ = self.checkQuestionnaireTimelimit(
                    session, sender_id, current_timestamp, questionnaire_name
                )
                entry = self._questionnaire_state_query(
                    session, sender_id, current_timestamp, questionnaire_name
                ).first()
                if entry is not None and entry.state != "to_be_stored":
                    return True, entry.state
                else:
                    return False, None
            except:
                logger.error(
                    f"Couldn't retrieve information for\nUserID: {sender_id}\nQuestionnaire: {questionnaire_name}"
                )
                return False, None

    def isFirstTimeToday(self, sender_id: str) -> bool:
        """
        Check if user has already interacted with the bot today.

        Args:
        - sender_id (str): User identifier.

        Returns:
        - bool: True if it's the user's first interaction with the bot today, False otherwise.
        """

        if sender_id[: len(sender_id) - 2].upper() in questionnaire_per_usecase.keys():
            return True
        else:
            with self.session_scope() as session:
                return self._first_time_of_day_query(session, sender_id)

    def checkQuestionnaireTimelimit(
        self,
        session: Session,
        sender_id: str,
        current_timestamp: float,
        questionnaire_name: str,
    ) -> SQLQuestState:
        """
        Checks whether a user has completed a questionnaire within the allowed time limit.
        If the time limit has been exceeded, creates a new database entry for the questionnaire
        with a new available timestamp.

        Args:
        - session (Session): A SQLAlchemy session object for the database
        - sender_id (str): A string representing the unique identifier for the user
        - current_timestamp (float): A float representing the current timestamp
        - questionnaire_name (str): A string representing the name of the questionnaire

        Returns:
        - (SQLQuestState): A SQLQuestState object representing the state of the questionnaire
        """

        entry = self._questionnaire_state_query(
            session, sender_id, current_timestamp, questionnaire_name
        ).first()
        if entry.state == "to_be_stored":
            return entry

        # this step might need to happen somewhere else, myb automatically
        # checks whether 1 or 2 days has passed after the questionnaire was first available
        usecase = sender_id[: len(sender_id) - 2].upper()
        today = (
            datetime.datetime.now(pytz.timezone(self.getUserTimezone(sender_id)))
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .timestamp()
        )  # timezone doesnt really matter hear as timestamps are universal
        # questionnaire are always available for the demo ids
        if (
            usecase not in questionnaire_per_usecase.keys()
            and self.getUserUsecase(sender_id).upper() != "STROKE"
        ):
            df_row = schedule_df.loc[
                schedule_df["questionnaire_abvr"] == entry.questionnaire_name
            ]
            lifespanInDays = int(df_row["lifespanInDays"].values[0])

            time_limit = (
                datetime.datetime.fromtimestamp(entry.available_at)
                + datetime.timedelta(days=lifespanInDays)
            ).timestamp()

            if time_limit < current_timestamp:
                entry.state = "incomplete"

                # create new database entry
                # doing this everyday for the msdomain_daily might not be so efficient
                tz_timezone = pytz.timezone(self.getUserTimezone(sender_id))
                last_availability = datetime.datetime.fromtimestamp(
                    entry.available_at, tz=tz_timezone
                )
                new_timestamp = getNextQuestTimestamp(
                    schedule_df,
                    entry.questionnaire_name,
                    last_availability,
                    tz_timezone,
                )
                while new_timestamp < today:
                    new_timestamp = getNextQuestTimestamp(
                        schedule_df,
                        entry.questionnaire_name,
                        datetime.datetime.fromtimestamp(new_timestamp),
                        tz_timezone,
                    )

                session.add(
                    self.SQLQuestState(
                        sender_id=sender_id,
                        questionnaire_name=entry.questionnaire_name,
                        available_at=new_timestamp,
                        state="available",
                        timestamp_start=None,
                        timestamp_end=None,
                        answers=None,
                        scoring=None,
                    )
                )
        session.commit()
        return entry

    def getAvailableQuestionnaires(
        self, sender_id: str, current_timestamp: float
    ) -> Tuple[List[str], List[str]]:
        """
        Retrieve current available questionnaires.

        Args:
        - sender_id (str): the unique identifier of the user.
        - current_timestamp (float): the current timestamp in Unix format.

        Returns:
        - Tuple[List[str], List[str]]: a tuple containing a list of available questionnaires
        and a list of questionnaires that need to be reset.
        """

        available_questionnaires, reset_questionnaires = [], []
        with self.session_scope() as session:
            database_entries = self._questionnaire_state_query(
                session, sender_id, current_timestamp
            ).all()
            if len(database_entries) == 0:
                return available_questionnaires, reset_questionnaires
            for entry in database_entries:
                if entry.state == "to_be_stored":
                    continue

                # this step might need to happen somewhere else, myb automatically
                # checks whether 1 or 2 days has passed after the questionnaire was first available
                usecase = sender_id[: len(sender_id) - 2].upper()

                # the first if-branch checks whether the id is a demoID (starting from ms or stroke or is an official
                # STROKE id given by WCS. If it is neither cases then it should be an official MS id given by WCS.
                if (
                    usecase not in questionnaire_per_usecase.keys()
                    and self.getUserUsecase(sender_id).upper() != "STROKE"
                ):
                    df_row = schedule_df.loc[
                        schedule_df["questionnaire_abvr"] == entry.questionnaire_name
                    ]
                    lifespanInDays = int(df_row["lifespanInDays"].values[0])
                    time_limit = (
                        datetime.datetime.fromtimestamp(entry.available_at)
                        + datetime.timedelta(days=lifespanInDays)
                    ).timestamp()

                    if time_limit < current_timestamp:
                        entry.state = "incomplete"

                        # create new database entry
                        # doing this everyday for the msdomain_daily might not be so efficient
                        today = (
                            datetime.datetime.now(
                                pytz.timezone(self.getUserTimezone(sender_id))
                            )
                            .replace(hour=0, minute=0, second=0, microsecond=0)
                            .timestamp()
                        )  # timezone doesnt really matter hear as timestamps are universal
                        tz_timezone = pytz.timezone(self.getUserTimezone(sender_id))
                        last_availability = datetime.datetime.fromtimestamp(
                            entry.available_at, tz=tz_timezone
                        )
                        new_timestamp = getNextQuestTimestamp(
                            schedule_df,
                            entry.questionnaire_name,
                            last_availability,
                            tz_timezone,
                        )
                        while new_timestamp < today:
                            new_timestamp = getNextQuestTimestamp(
                                schedule_df,
                                entry.questionnaire_name,
                                datetime.datetime.fromtimestamp(new_timestamp),
                                tz_timezone,
                            )

                        session.add(
                            self.SQLQuestState(
                                sender_id=sender_id,
                                questionnaire_name=entry.questionnaire_name,
                                available_at=new_timestamp,
                                state="available",
                                timestamp_start=None,
                                timestamp_end=None,
                                answers=None,
                                scoring=None,
                            )
                        )

                        # questionnaires that are passed the time limit need to be reset
                        reset_questionnaires.append(entry.questionnaire_name)
                    else:
                        # when the questionnaire becomes available again, reset its slots
                        if entry.state == "available":
                            reset_questionnaires.append(entry.questionnaire_name)
                        available_questionnaires.append(entry.questionnaire_name)
                else:
                    if entry.state == "available":
                        reset_questionnaires.append(entry.questionnaire_name)
                    available_questionnaires.append(entry.questionnaire_name)
            session.commit()
        return available_questionnaires, reset_questionnaires

    def sendQuestionnaireScoreToOntology(
        self,
        session: Session,
        tracker: DialogueStateTracker,
        sender_id: str,
        questionnaire_name: str,
        database_entry: Dict,
        total_score: Optional[float] = None,
        sub_scores: Dict[str, float] = {},
    ) -> None:
        """
        Store the questionnaire score to the local database and send it to the ontology.

        Score only available for:
        - muscletone
        - psqi

        Args:
            session (Session): A SQLAlchemy session object for the database
            tracker (DialogueStateTracker): Tracker object to retrieve the user access token.
            sender_id (str): ID of the user who completed the questionnaire.
            questionnaire_name (str): Name of the questionnaire.
            database_entry (Dict): Dictionary containing the database entry for the questionnaire.
            total_score (Optional[float], optional): The total score of the questionnaire. Defaults to None.
            sub_scores (Dict[str, float], optional): The sub-scores of the questionnaire. Defaults to {}.
        """

        questionnaires = {
            "psqi": "Pittsburgh Sleep Quality Index",
            "muscletone": "Muscle Tone",
        }

        score_list = []
        if not total_score:
            total_score = self._questionnaire_score_query(
                session, sender_id, questionnaire_name
            )
        score_list.append({"score": total_score, "scoreDescription": "TOTAL"})

        ontology_data = {
            "user_id": sender_id,
            "source": "CA",
            "survey_title": questionnaires[questionnaire_name],
            "partner": "UPB",
            "disease": "STROKE",
            "abbreviation": questionnaire_name,
            "submission_date": database_entry["submission_date"],
            "survey_score": score_list,
        }

        # Send scores to ontology
        print(f"*****Store scores to ontology: {ontology_data}*****")
        ontology_endpoint = endpoints_df[
            endpoints_df["name"] == "ONTOLOGY_SEND_SCORE_ENDPOINT"
        ]["endpoint"].values[0]
        user_accessToken = tracker.get_slot("user_accessToken")

        try:
            response = requests.post(
                ontology_endpoint,
                json=ontology_data,
                timeout=30,
                auth=BearerAuth(user_accessToken),
            )
            response.close()

            if response.status_code == 200 or 201:
                print("Scores successfully stored in ontology")
            else:
                print(
                    f"Failed to store scores in ontology for\nUserID: {sender_id}\nQuestionnaire: {questionnaire_name}\nwith {response}"
                )
        except TypeError as error:
            logger.error(
                "In custom_tracker_store function sendQuestionnaireScoreToOntology",
                exc_info=True,
            )
            print(
                f"In custom_tracker_store function sendQuestionnaireScoreToOntology\n{error}"
            )

    def saveToOntology(self, tracker: DialogueStateTracker, sender_id: str) -> None:
        """
        Data send to ontology should hold a specific format given below.

        {
            "user_id": "b292b4c3-7d36-4991-a1b2-5055f16489bc",
            "source": "Conversational Agent",
            "observations": [
                {
                "sentiment_scores": [
                    {
                    "sentiment_class": "Positive",
                    "sentiment_score": 87.0
                    },
                    {
                    "sentiment_class": "Neutral",
                    "sentiment_score": 2.0
                    },
                    {
                    "sentiment_class": "Negative",
                    "sentiment_score": 11.0
                    }
                ],
                "timestamp": "2022-05-17T16:19:55Z",
                "explanation": "I feel great",
                "on_dashboard": "False"
                },
                {
                "sentiment_scores": [
                    {
                    "sentiment_class": "Positive",
                    "sentiment_score": 3.0
                    },
                    {
                    "sentiment_class": "Neutral",
                    "sentiment_score": 27.0
                    },
                    {
                    "sentiment_class": "Negative",
                    "sentiment_score": 70.0
                    }
                ],
                "timestamp": "2022-05-17T16:37:34Z",
                "explanation": "I fell down the stairs yesterday",
                "on_dashboard": "True"
                }
            ]
        }

        Args:
        - tracker: A tracker object containing conversation state information.
        - sender_id: A string containing the user ID.

        Returns:
        - None
        """

        # Building ontology payload
        ontology_data = {
            "user_id": sender_id,
            "source": "Conversational Agent",
            "observations": [],
        }
        with self.session_scope() as session:
            print("Quering the database to get sentiment")
            message_entries, include_in_report_intents = self._sentiment_query(
                session, sender_id
            )
            intent_to_bool = {"affirm": True, "deny": False, "cancel": False}

            for (msg_type, message), intent in zip(
                message_entries.items(), include_in_report_intents
            ):
                if msg_type == "message":
                    try:
                        message_data = json.loads(message.data)
                    except (AttributeError, ValueError, TypeError) as error:
                        logger.error("Couldn't retrieve message data.", exc_info=True)
                        message_text = {"message": "Default"}
                        message_data = {
                            "parse_data": {
                                "entities": [
                                    {
                                        "value": "neu",
                                        "confidence": 80,
                                        "entity": "sentiment",
                                        "extractor": "sentiment_extractor",
                                    },  # dummy data
                                    # add default data
                                    {
                                        "value": [
                                            {
                                                "sentiment_class": "positive",
                                                "sentiment_score": 10.0,
                                            },
                                            {
                                                "sentiment_class": "neutral",
                                                "sentiment_score": 80.0,
                                            },
                                            {
                                                "sentiment_class": "negative",
                                                "sentiment_score": 10.0,
                                            },
                                        ]
                                    },
                                ]
                            }
                        }

                    message_sentiment = (
                        message_data.get("parse_data", {})
                        .get("entities", {})[1]
                        .get("value")
                    )
                    # TODO Add here a try/except block in case there is no message object to add a default timestamp
                    timestamp = datetime.datetime.fromtimestamp(
                        message.timestamp
                    ).strftime("%Y-%m-%dT%H:%M:%SZ")
                    message_text = message.message
                elif msg_type == "slot":
                    message_sentiment = json.loads(message[1].data).get("value")
                    timestamp = datetime.datetime.fromtimestamp(
                        message[0].timestamp
                    ).strftime("%Y-%m-%dT%H:%M:%SZ")
                    message_text = json.loads(message[0].data).get("value")

                # this change is required to match the ontolody format
                # this might be removed in the future
                temp_sentiment = json.dumps(message_sentiment)
                temp_sentiment = temp_sentiment.replace("positive", "Positive")
                temp_sentiment = temp_sentiment.replace("negative", "Negative")
                temp_sentiment = temp_sentiment.replace("neutral", "Neutral")

                data = {
                    "sentiment_scores": json.loads(temp_sentiment),
                    "timestamp": timestamp,
                    "explanation": message_text,
                    "on_dashboard": intent_to_bool[intent],
                }
                ontology_data["observations"].append(data)
            session.commit()

        # Store data to ontology
        print(f"*****Store data to ontology*****")
        ontology_ca_endpoint = endpoints_df[
            endpoints_df["name"] == "ONTOLOGY_CA_ENDPOINT"
        ]["endpoint"].values[0]
        user_accessToken = tracker.get_slot("user_accessToken")

        try:
            response = requests.post(
                ontology_ca_endpoint,
                json=ontology_data,
                timeout=45,
                auth=BearerAuth(user_accessToken),
            )
            response.close()

            if response.status_code == 200 or 201:
                print("Successfully stored data to ontology")
            else:
                print(f"Failed to store data to ontology with {response}")
        except TypeError as error:
            logger.error(f"Couldn't store data on to ontology", exc_info=True)
            print(f"In custom_tracker_store function saveToOntology\n{error}")

    def registerUserIDdemo(self, sender_id: str, usecase: str) -> str:
        """Checks if the specific user id is in the database. If not, it adds it.

        Args:
            self: An instance of the class.
            sender_id: A string representing the ID of the sender.
            usecase: A string representing the usecase of the user.

        Returns:
            A string representing the language of the user.

        """

        with self.session_scope() as session:
            # assumes user ids are of the form "ms00" or "stroke00"
            if usecase == "MS":
                language = "Italian"
                timezone = "Europe/Brussels"
            elif usecase == "STROKE":
                language = "Romanian"
                timezone = "Europe/Bucharest"
            elif usecase == "PD":
                language = "Greek"
                timezone = "Europe/Athens"

            now = datetime.datetime.now(tz=pytz.utc)
            session.add(
                self.SQLUserID(
                    sender_id=sender_id,
                    usecase=usecase,
                    language=language,
                    onboarding_timestamp=now.timestamp(),
                    timezone=timezone,
                )
            )

            # add the corresponding questionnaires based on the usecase
            # change time to local time and then back to utc
            tz_timezone = pytz.timezone(timezone)
            now = now.astimezone(tz_timezone)
            now = now.replace(hour=0, minute=0, second=0, microsecond=0)
            for questionnaire in questionnaire_per_usecase[usecase]:
                # timestamp = (now + datetime.timedelta(days=1)).timestamp()
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
                        scoring=None,
                    )
                )
            session.commit()
        return language

    def checkUserID(self, sender_id: str, ca_accessToken: str) -> str:
        """
        Checks if the specific user id is in the database. If not:
        - adds the user id and his/her onboarding date on the information provided by WCS
        - adds the first set of questionnaires

        Args:
        - tracker (DialogueStateTracker): tracker object from Rasa framework
        - sender_id (str): ID of the user
        - status_code (int): HTTP status code returned by WCS endpoint
        - ca_accessToken (str): access token for WCS

        Returns:
        - language (str): the language of the user, either retrieved from WCS or assigned by default
        """

        with self.session_scope() as session:
            user_entry = (
                session.query(self.SQLUserID)
                .filter(self.SQLUserID.sender_id == sender_id)
                .first()
            )
            if user_entry is None:
                usecase = sender_id[: len(sender_id) - 2].upper()
                if usecase in questionnaire_per_usecase.keys():
                    language = self.registerUserIDdemo(sender_id, usecase)
                else:
                    try:
                        wcs_endpoint = endpoints_df[
                            endpoints_df["name"] == "WCS_ONBOARDING_ENDPOINT"
                        ]["endpoint"].values[0]
                        response = requests.get(
                            wcs_endpoint,
                            params={"patient_uuid": sender_id},
                            timeout=30,
                            auth=BearerAuth(ca_accessToken),
                        )
                        logger.debug(
                            f"Get data from WCS for userid {sender_id} - {response}"
                        )
                        print(f"Get data from WCS for userid {sender_id} - {response}")
                        response.close()
                        resp = response.json()
                        partner = resp["partner"]

                        if partner == "FISM":
                            usecase = "MS"
                            language = "Italian"
                            timezone = "Europe/Brussels"
                        elif partner == "SUUB":
                            usecase = "STROKE"
                            language = "Romanian"
                            timezone = "Europe/Bucharest"
                        elif partner == "NKUA":
                            usecase = "PD"
                            language = "Greek"
                            timezone = "Europe/Athens"
                        else:
                            usecase = "None"
                            language = "English"
                            timezone = "UTC"

                        wcs_registration_date = resp["registration_date"]
                        registration_date = datetime.datetime.strptime(
                            wcs_registration_date, "%Y-%m-%d"
                        )

                        tz_timezone = pytz.timezone(timezone)
                        tz_registration_date = registration_date.astimezone(tz_timezone)
                        tz_registration_date = tz_registration_date.replace(
                            hour=0, minute=0, second=0, microsecond=0
                        )
                        registration_timestamp = registration_date.timestamp()

                        session.add(
                            self.SQLUserID(
                                sender_id=sender_id,
                                usecase=usecase,
                                language=language,
                                onboarding_timestamp=registration_timestamp,
                                timezone=timezone,
                            )
                        )
                        session.commit()

                        df_questionnaires = schedule_df[
                            schedule_df["usecase"] == usecase
                        ]
                        # onboarding_date = datetime.datetime.strptime(registration_date, "%Y-%m-%d")
                        # onboarding_timestamp = onboarding_date.replace(hour=0, minute=0, second=0, microsecond=0)

                        now = datetime.datetime.now(tz=tz_timezone)
                        today = now.replace(
                            hour=0, minute=0, second=0, microsecond=0
                        ).timestamp()
                        if usecase == "MS":
                            for questionnaire in df_questionnaires[
                                "questionnaire_abvr"
                            ]:
                                first_monday = (
                                    tz_registration_date
                                    + datetime.timedelta(
                                        days=(0 - tz_registration_date.weekday()) % 7
                                    )
                                )
                                # doing this everyday for the msdomain_dialy might not be so efficient
                                if questionnaire == "MSdomainIV_Daily":
                                    timestamp = today
                                else:
                                    timestamp = getFirstQuestTimestamp(
                                        schedule_df,
                                        questionnaire,
                                        first_monday,
                                        tz_timezone,
                                    )
                                    while timestamp < today:
                                        timestamp = getNextQuestTimestamp(
                                            schedule_df,
                                            questionnaire,
                                            datetime.datetime.fromtimestamp(
                                                timestamp, tz=tz_timezone
                                            ),
                                            tz_timezone,
                                        )
                                session.add(
                                    self.SQLQuestState(
                                        sender_id=sender_id,
                                        questionnaire_name=questionnaire,
                                        available_at=timestamp,
                                        state="available",
                                        timestamp_start=None,
                                        timestamp_end=None,
                                        answers=None,
                                        scoring=None,
                                    )
                                )
                            session.commit()
                        elif usecase == "STROKE":
                            for questionnaire in df_questionnaires[
                                "questionnaire_abvr"
                            ]:
                                session.add(
                                    self.SQLQuestState(
                                        sender_id=sender_id,
                                        questionnaire_name=questionnaire,
                                        available_at=today,
                                        state="available",
                                        timestamp_start=None,
                                        timestamp_end=None,
                                        answers=None,
                                        scoring=None,
                                    )
                                )
                            session.commit()
                    except:
                        if sender_id and sender_id not in ["null", "default"]:
                            session.add(
                                self.SQLIssue(
                                    sender_id=sender_id,
                                    timestamp=datetime.datetime.now().timestamp(),
                                    description="failed to retrieve user info from wcs endpoint",
                                )
                            )
                        language = "English"
                        logger.error(
                            f"Failed to retrieve user info from WCS endpoint for\nuserID:{sender_id}"
                        )
                session.commit()
            else:
                # is the user already exists in the database retrieve their language
                language = user_entry.language

        return language

    def getUserTimezone(self, sender_id: str) -> str:
        """
        Retrieves the specific user's timezone from the database.

        Args:
            sender_id (str): The ID of the user whose timezone is to be retrieved.

        Returns:
            str: The timezone of the user.
        """
        with self.session_scope() as session:
            user_entry = (
                session.query(self.SQLUserID)
                .filter(self.SQLUserID.sender_id == sender_id)
                .first()
            )
        return user_entry.timezone

    def getUserUsecase(self, sender_id: str) -> str:
        """
        Retrieves the specific user's usecase from the database.

        Args:
            sender_id (str): The ID of the user whose usecase is to be retrieved.

        Returns:
            str: The usecase of the user.
        """
        with self.session_scope() as session:
            user_entry = (
                session.query(self.SQLUserID)
                .filter(self.SQLUserID.sender_id == sender_id)
                .first()
            )
        return user_entry.usecase

    def getUserDetails(self, sender_id: str) -> Tuple[str, str]:
        """
        Get specific user's partner name and disease based on their usecase.

        Args:
            sender_id (str): The ID of the user whose details are to be retrieved.

        Returns:
            Tuple[str, str]: A tuple containing the partner name and disease of the user.
        """
        usecase = self.getUserUsecase(sender_id)
        if usecase == "MS":
            return "FISM", "MULTIPLE_SCLEROSIS"
        elif usecase == "STROKE":
            return "SUUB", "STROKE"
        elif usecase == "PD":
            return "NKUA", "PARKINSONS"
        else:
            return "N/A", "N/A"

    def logTechIssue(self, issue: str, sender_id: str) -> None:
        """
        Logs technical issues as reported by users.

        Args:
            issue (str): The description of the technical issue reported by the user.
            sender_id (str): The ID of the user who reported the issue.
        """
        with self.session_scope() as session:
            session.add(
                self.SQLIssue(
                    sender_id=sender_id,
                    timestamp=datetime.datetime.now().timestamp(),
                    description="Patient reported:" + issue,
                )
            )
            session.commit()

    def sendQuestionnaireStatus(
        self,
        tracker: DialogueStateTracker,
        sender_id: str,
        questionnare_abvr: str,
        status: str,
    ) -> None:
        """
        Sends the status of the questionnaire to WCS

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

        Args:
            - tracker (DialogueStateTracker): tracker object from Rasa framework
            - sender_id (str): ID of the sender.
            - questionnare_abvr (str): abbreviation of the questionnaire.
            - status (str): status of the questionnaire.

        Raises:
            KeyError: if questionnare_abvr is not supported.
        """

        submission_date = datetime.datetime.now(datetime.timezone.utc)
        questionnaire_data = {
            "patient_uuid": sender_id,
            "abbreviation": questionnare_abvr,
            "status": status,
            "submission_date": submission_date.strftime("%Y-%m-%d"),
        }

        # msdomainIV check again
        if questionnare_abvr in [
            "MSdomainIV_Daily",
            "STROKEdomainIV",
            "STROKEdomainV",
            "STROKEdomainIV",
        ]:
            with self.session_scope() as session:
                answers_events = self._questionnaire_answers_query(
                    session, sender_id, questionnare_abvr
                )
                answers = json.loads(answers_events.answers)
                # remove the timestamp of each message
                res_answers = [
                    {key: val for key, val in d.items() if key != "timestamp"}
                    for d in answers
                ]
                session.commit()
            questionnaire_data["questionnaire_answers"] = res_answers
        elif questionnare_abvr == "dizzNbalance":
            new_symptoms = self.getDizzinessNbalanceNewSymptoms(sender_id)
            areNewSymptoms = str(len(new_symptoms) > 0)
            questionnaire_data["questionnaire_answers"] = [
                {
                    "number": "Symptoms",
                    "question": "SYMPTOMS: Select all that apply and press send:",
                    "answer": areNewSymptoms,
                }
            ]

        print(10 * "=" + " Sending questionaire data to WCS " + 10 * "=")
        wcs_status_endpoint = endpoints_df[
            endpoints_df["name"] == "WCS_STATUS_ENDPOINT"
        ]["endpoint"].values[0]
        user_accessToken = tracker.get_slot("user_accessToken")

        try:
            response = requests.post(
                wcs_status_endpoint,
                json=questionnaire_data,
                timeout=30,
                auth=BearerAuth(user_accessToken),
            )
            response.close()

            if response.status_code == 200 or 201:
                print("Successfully sent data to WCS")
            else:
                print(f"Failed to send data to WCS with {response}")
        except TypeError as error:
            print(
                f"Sending questionnaire data to WCS failed in sendQuestionnaireStatus\n{error}"
            )

    def getDizzinessNbalanceNewSymptoms(self, sender_id: str) -> List[(str)]:
        """
        Gets the symptoms of the latest Dizziness and Balance questionnaire and of the one before that
        Compares the symptoms and sends all new symptoms to wcs for the alert mechanism

        Args:
            sender_id (str): the id of the sender/patient

        Returns:
            list of str: a list containing the new symptoms
        """
        with self.session_scope() as session:
            answers_events, previous_answers_events = self._questionnaire_answers_query(
                session, sender_id, "dizzNbalance", False, 1
            )
            answers = json.loads(answers_events.answers)
            new_symptoms = []
            if previous_answers_events:
                previous_answers = json.loads(previous_answers_events[0].answers)
                symptoms = [
                    answer["answer"]
                    for answer in answers
                    if answer["number"] == "Symptoms"
                ]
                previous_symptoms = [
                    answer["answer"]
                    for answer in previous_answers
                    if answer["number"] == "Symptoms"
                ]
                # do this because anwers are in the form ["symptom1, symptom2"]
                symptoms = symptoms[0].split(", ")
                previous_symptoms = previous_symptoms[0].split(", ")
                new_symptoms = [x for x in symptoms if x not in previous_symptoms]
            session.commit()
            return new_symptoms


def getFirstQuestTimestamp(schedule_df, questionnaire_name, init_date, tz_timezone):
    """Get the date the specified questionnaire will be available for the first time
    Args:
        schedule_df: pandas dataframe containing the schedule
        questionnaire_name:
        init_date: initial date in datetime format
    Returns:
        timestamp

    NOTE: always use timezone aware datetime objects
    """
    df_row = schedule_df.loc[schedule_df["questionnaire_abvr"] == questionnaire_name]
    dayOfWeek = int(df_row["dayOfWeek"].values[0])
    weekOfMonth = int(df_row["weekOfMonth"].values[0])
    frequencyInWeeks = int(df_row["frequencyInWeeks"].values[0])
    # if the questionnaire is not available in the current month
    if frequencyInWeeks > 4:
        weekOfMonth = frequencyInWeeks - 1

    if questionnaire_name == "MSdomainIV_Daily":
        q_day = init_date.timestamp()
        # q_day = getNextKTimestamps(init_date,1)[0]
    else:
        q_day_tmp = init_date + datetime.timedelta(
            days=dayOfWeek, weeks=max(0, weekOfMonth - 1)
        )
        q_day = getDSTawareDate(init_date, q_day_tmp, tz_timezone).timestamp()
    return q_day


def getNextQuestTimestamp(schedule_df, questionnaire_name, init_date, tz_timezone):
    """Get the next date the specified questionnaire will be available given an intial date
    Args:
        schedule_df: pandas dataframe containing the schedule
        questionnaire_name:
        init_date: initial date in datetime format
    Returns:
        timestamp

    NOTE: always use timezone aware datetime objects
    """
    df_row = schedule_df.loc[schedule_df["questionnaire_abvr"] == questionnaire_name]
    frequencyInWeeks = int(df_row["frequencyInWeeks"].values[0])

    if questionnaire_name == "MSdomainIV_Daily":
        q_day = getNextKTimestamps(init_date, tz_timezone, 1)[0]
    else:
        q_day_tmp = init_date + datetime.timedelta(weeks=frequencyInWeeks)
        q_day = getDSTawareDate(init_date, q_day_tmp, tz_timezone).timestamp()
    return q_day


def getNextKTimestamps(init_date, tz_timezone, number_of_days: int = 7):
    """Get the next (number_of_days) timestamps after an intial date
    Args:
        init_date: initial date in datetime format
        number_of_days: number of next days
    Returns:
        timestamp

    NOTE: always use timezone aware datetime objects
    """
    q_days = []
    for i in range(number_of_days):
        q_day_tmp = init_date + datetime.timedelta(days=i + 1)
        q_day = getDSTawareDate(init_date, q_day_tmp, tz_timezone).timestamp()
        q_days.append(q_day)
    return q_days


def getDSTawareDate(init_date, new_date, tz_timezone):
    """Converts the new_date into a datetime object that takes into account the daylight saving changes (dst) based on the init_date
    Code from: https://www.hacksoft.io/blog/handling-timezone-and-dst-changes-with-python
    """
    init_date = init_date.astimezone(tz_timezone)
    new_date = new_date.astimezone(tz_timezone)

    dst_offset_diff = init_date.dst() - new_date.dst()

    new_date = new_date + dst_offset_diff
    new_date = new_date.astimezone(tz_timezone)

    return new_date


# if __name__ == "__main__":
#     ts = CustomSQLTrackerStore(db="G:\\.shortcut-targets-by-id\\1UxkjI9sIqZr2t87jpGt5qjUHgA1tMcyT\\ALAMEDA\\Zenon\\db BackUps\\backUp-20231904.db")
# print(ts.sendQuestionnaireStatus("631327a2-0b50-417a-8c1d-625d84c5114a", "STROKEdomainIV", "COMPLETED"))

# print(datetime.datetime.now().timestamp())
# now = datetime.datetime.today()
# first_monday = now + datetime.timedelta(days=(0-now.weekday())%7)
# q_day = first_monday + datetime.timedelta(days=5, weeks=max(0,4-1))
# print(q_day.timestamp())

# with ts.session_scope() as session:
#     sender_id = "91175647-bbd4-4ea5-a1b2-13c491e1b076"
#     current_timestamp = datetime.datetime.now().timestamp()
# print(ts._questionnaire_state_query(session, sender_id, current_timestamp).all())
# print(ts.checkQuestionnaireTimelimit(session, sender_id, current_timestamp, "MSdomainIV_Daily"))
# print(ts.getAvailableQuestionnaires(sender_id, current_timestamp))
# session_start_timestamp = session.query(sa.func.max(ts.SQLEvent.timestamp)).filter(
#         ts.SQLEvent.sender_id == "91175647-bbd4-4ea5-a1b2-13c491e1b076",
#         ts.SQLEvent.type_name == SessionStarted.type_name,
#     ).first()[0]

# print(session_start_timestamp)
# message_entry = session.query(ts.SQLEvent).filter(
#     ts.SQLEvent.sender_id == "91175647-bbd4-4ea5-a1b2-13c491e1b076",
#     ts.SQLEvent.type_name == "user",
#     ts.SQLEvent.intent_name == "inform",
#     ts.SQLEvent.timestamp >= 1678571115.89694,
# ).order_by(ts.SQLEvent.timestamp).first()

# print(message_entry.data)

# message_entries, report = ts._sentiment_query(session, sender_id)
# print(message_entries)
# print(25*"=")
# print(report)
