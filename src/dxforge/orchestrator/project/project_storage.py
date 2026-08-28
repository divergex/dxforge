from orchestrator.db import MetadataStore
from ..storage import Storage


class ProjectStorage:
    def __init__(self, store: MetadataStore, storage: Storage):
        self.store = store  # Handles stored project data
        self.storage = storage  # Handles file storage

    def upload_project(self, project_id: str, zip_path: str):
        self.storage.upload_zip(project_id, zip_path)

    def upload_files(self, project_id: str, dir_path: str):
        self.storage.upload_dir(project_id, dir_path)
