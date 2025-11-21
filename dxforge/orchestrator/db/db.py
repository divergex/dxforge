from abc import abstractmethod, ABC
from typing import Optional
from pymongo import MongoClient, errors
import os
import time
import logging


class DBHelper(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        pass

    @abstractmethod
    def close(self):
        pass

    def get_collection(self, collection_name: str):
        raise NotImplementedError("get_collection not implemented for this DBHelper")


class MongoDB(DBHelper):
    """
    MongoDB helper class for safe and configurable access.
    """
    def __init__(
            self,
            host: Optional[str] = None,
            port: Optional[int] = None,
            db_name: Optional[str] = None,
            username: Optional[str] = None,
            password: Optional[str] = None,
            uri: Optional[str] = None,
            max_retries: int = 5,
            retry_delay: float = 1.0,
            connection_timeout: Optional[float] = 1000,
            logger: Optional[logging.Logger] = None
    ):
        """
        Initialize connection parameters. Environment variables fallback:
            MONGO_HOST, MONGO_PORT, MONGO_DB, MONGO_USER, MONGO_PASSWORD
        """
        super().__init__()

        self.host = host or os.environ.get("MONGO_HOST", "localhost")
        self.port = port or int(os.environ.get("MONGO_PORT", 27017))
        self.db_name = db_name or os.environ.get("MONGO_DB", "dxforge")
        self.username = username or os.environ.get("MONGO_USER")
        self.password = password or os.environ.get("MONGO_PASSWORD")
        self.uri = uri or os.environ.get("MONGO_URI")

        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.connection_timeout = connection_timeout

        self.client: Optional[MongoClient] = None
        self.db = None

        self.logger = logger or logging.getLogger(__name__)

    def is_connected(self) -> bool:
        return self.db is not None

    def connect(self) -> None:
        """
        Connect to MongoDB, retrying if necessary.
        """
        attempts = 0
        while attempts < self.max_retries:
            try:
                if self.uri:
                    self.client = MongoClient(self.uri, serverSelectionTimeoutMS=self.connection_timeout)
                else:
                    self.client = MongoClient(
                        host=self.host,
                        port=self.port,
                        username=self.username,
                        password=self.password,
                        serverSelectionTimeoutMS=self.connection_timeout,
                    )
                # Trigger server selection to verify connection
                self.client.admin.command("ping")
                self.db = self.client.get_database(self.db_name)
                return
            except (errors.ConnectionFailure, errors.ServerSelectionTimeoutError) as e:
                attempts += 1
                self.logger.warning(f"MongoDB connection attempt {attempts} failed: {e}")
                if attempts >= self.max_retries:
                    raise ConnectionError(f"Failed to connect to MongoDB after {attempts} attempts: {e}")
                time.sleep(self.retry_delay)

    def get_collection(self, collection_name: str):
        """
        Safely retrieve a collection.
        """
        if not self.is_connected():
            raise ConnectionError("MongoDB is not connected. Call connect() first.")
        return self.db[collection_name]

    def ensure_collection(self, collection_name: str, **kwargs):
        """
        Optionally create collection with options if it does not exist.
        """
        if not self.is_connected():
            raise ConnectionError("MongoDB is not connected. Call connect() first.")
        if collection_name not in self.db.list_collection_names():
            self.db.create_collection(collection_name, **kwargs)
        return self.db[collection_name]

    def list_collections(self):
        if not self.is_connected():
            raise ConnectionError("MongoDB is not connected. Call connect() first.")
        return self.db.list_collection_names()

    def close(self):
        if self.client:
            self.client.close()
            self.client = None
        if self.db:
            self.db = None