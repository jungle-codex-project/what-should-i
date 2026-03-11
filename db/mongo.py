import logging

import mongomock
from flask import current_app
from pymongo import ASCENDING, DESCENDING, MongoClient


LOGGER = logging.getLogger(__name__)


class MongoManager:
    def __init__(self):
        self.client = None
        self.db = None
        self.is_mock = False

    def init_app(self, app):
        mongo_uri = app.config["MONGO_URI"]
        db_name = app.config["MONGO_DB_NAME"]

        try:
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=1500)
            client.admin.command("ping")
            self.client = client
            self.db = client[db_name]
            self.is_mock = False
        except Exception as exc:
            if not app.config.get("USE_MOCK_ON_FAILURE", True):
                raise
            LOGGER.warning("MongoDB connection failed. Falling back to mongomock: %s", exc)
            self.client = mongomock.MongoClient()
            self.db = self.client[db_name]
            self.is_mock = True

        app.extensions["mongo_manager"] = self
        self.ensure_indexes()

    def ensure_indexes(self):
        self.db.users.create_index([("email", ASCENDING)], unique=True)
        self.db.profiles.create_index([("user_id", ASCENDING)], unique=True)
        self.db.recommendation_history.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        self.db.trend_cache.create_index([("generated_at", DESCENDING)])
        self.db.quiz_logs.create_index([("quiz_id", ASCENDING), ("created_at", DESCENDING)])
        self.db.content_feedback.create_index([("user_id", ASCENDING), ("content_id", ASCENDING)], unique=True)
        self.db.content_source_cache.create_index([("cache_key", ASCENDING)], unique=True)
        self.db.content_source_cache.create_index([("generated_at", DESCENDING)])


mongo = MongoManager()


def get_db():
    manager = current_app.extensions["mongo_manager"]
    return manager.db


def get_collection(name: str):
    return get_db()[name]
