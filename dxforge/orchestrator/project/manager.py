import os
from typing import Optional
from uuid import uuid4, UUID

import docker

from orchestrator.db import Store, DBHelper
from orchestrator.storage import Storage

from .models import ProjectData


class Builder:
    def __init__(self, client: docker.DockerClient):
        self.client = client  # docker client

    def build(self, data: ProjectData, temp_path, tag: Optional[str] = None):
        dockerfile_str = data.build_data.dockerfile()
        dockerfile_path = os.path.join(temp_path, "Dockerfile")
        with open(dockerfile_path, "w") as f:
            f.write(dockerfile_str)

        image_tag = tag or f"{data.owner}/{data.name}:latest"

        image, logs = self.client.images.build(
            path=temp_path,  # path contains Dockerfile + app.py
            dockerfile="Dockerfile",
            rm=True,
            tag=image_tag,
            buildargs=data.build_data.build_args
        )

        return image


class ProjectManager:
    def __init__(self,
                 data: ProjectData,
                 uuid: Optional[UUID] = None,
                 db_helper: Optional[DBHelper] = None,
                 ):
        self.data = data
        self.uuid = uuid

        if db_helper:
            self.store = Store(db_helper, "projects")
            self.image_store = Store(db_helper, "images")
        else:
            self.store = None
        self.storage = None

    def setup(self, storage: Storage, db_helper: DBHelper):
        self.storage = storage
        self.store = Store(db_helper, "projects")
        self.image_store = Store(db_helper, "images")
        return self

    def create(self):
        self.uuid = uuid4()
        self.data.storage_path = self.storage_path
        self.store.create(ProjectData.__name__, self.uuid.hex, self.data)

    @classmethod
    def load(cls, uuid: UUID, storage: Storage, db_helper: DBHelper):
        store = Store(db_helper, "projects")
        if (metadata := store.get(ProjectData.__name__, {"document_id": uuid.hex})) is not None:
            manager = cls(metadata, uuid)
        else:
            raise Exception("Project not found")

        return manager.setup(storage, db_helper)

    @property
    def storage_path(self):
        return f"{ProjectData.__name__}/{self.data.owner}/{self.uuid.hex}/"

    def ensure_setup(self):
        if not self.storage:
            raise Exception("Storage not setup. Call the ProjectManager's instance .setup() method first.")
        if not self.store:
            raise Exception("Store not setup. Call the ProjectManager's instance .setup() method first.")

    def upload_zip(self, zip_path: str):
        self.storage.upload_zip(zip_path, self.storage_path)

    def upload_files(self, dir_path: str):
        self.storage.upload_dir(dir_path, self.storage_path)

    def build(self, client):
        self.ensure_setup()
        path = self.storage.download_to_tempdir(self.data.storage_path)
        builder = Builder(client)
        image = builder.build(self.data, path)



        return image
