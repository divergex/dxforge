import uuid
from datetime import datetime
from typing import Dict, Optional, List

from pydantic import BaseModel

from . import DBHelper
from .store import Store


class Container(BaseModel):
    project_id: str
    container_id: str
    status: Optional[str] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def index_fields(cls):
        return ["project_id", "container_id"]


class ContainerStore(Store):
    """
    Handles container persistence (MongoDB/Redis later).
    Stores container metadata and status.
    """
    def __init__(self, db_helper: DBHelper):
        super().__init__(db_helper, "containers")
        self.model_name = "container"
        self.containers_collection = self.db_helper.get_collection("containers")

        self._cache: Dict[str, Container] = {}
        self._load_cache()

        self.setup()

    def setup(self):
        # data_fields = Container.model_json_schema()["properties"]
        index_fields = Container.index_fields()
        index = [(f"data.{field}", 1) for field in index_fields]
        self.containers_collection.create_index(index, unique=True)

        self.register_model(self.model_name, Container)

    @staticmethod
    def cache_key(container: Container) -> str:
        return f"{container.project_id}:{container.container_id}"

    def _load_cache(self):
        for container in self.containers_collection.find():
            self._cache[self.cache_key(container)] = container

    def _save_to_cache(self, container: Container):
        self._cache[self.cache_key(container)] = container

    def _remove_from_cache(self, container: Container):
        self._cache.pop(self.cache_key(container), None)

    def create_container(self, project_id: str, container_id: str):
        document = Container(
            project_id=project_id,
            container_id=container_id,
            status="stopped",
            updated_at=datetime.now()
        )

        self.create(self.model_name, document_id := uuid.uuid4().hex, document=document)
        self._save_to_cache(document)
        return document_id

    def update_status(self, project_id: str, container_id: str, status: str):
        doc = self.partial_update(
            self.model_name,
            {"status": status, "updated_at": datetime.now()},
            data_filters={"project_id": project_id, "container_id": container_id}
        )
        if doc:
            data = doc["data"]
            container = Container(**data)
            self._save_to_cache(container)
        else:
            raise ValueError(f"Container with id {container_id} not found")

    def get_container(self, project_id: str, container_id: str, cached: Optional[bool] = True) -> Optional[Container]:
        temp_container = Container(project_id=project_id, container_id=container_id)
        if cached and (key := self.cache_key(temp_container)) in self._cache:
            return self._cache[key]
        return self.get(self.model_name, data_filters={"project_id": project_id, "container_id": container_id})

    def list_containers(self, project_id: Optional[str] = None, status: Optional[str] = None) -> List[Container]:
        query = {}
        if project_id:
            query["data.project_id"] = project_id
        if status:
            query["data.status"] = status
        docs = self.containers_collection.find(query)
        return [Container(**doc["data"]) for doc in docs]

    def delete_container(self, project_id: str, container_id: str):
        self.delete(self.model_name, data_filters={"project_id": project_id, "container_id": container_id})
        self._remove_from_cache(Container(project_id=project_id, container_id=container_id))
