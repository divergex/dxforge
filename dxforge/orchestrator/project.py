from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import shutil, zipfile

from .db import Base, User, Project
from .user import UserManager


class ProjectManager:
    def __init__(self, base_dir: str = "storage", db_path: str = "orchestrator.sqlite"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def create_project(self, owner_id: int, name: str, tag: str = None):
        with self.Session() as s:
            owner = s.get(User, owner_id)
            if not owner:
                raise ValueError("User not found")

            if s.query(Project).filter_by(owner=owner_id, name=name).first():
                raise ValueError("Project already exists")

            project_dir = self.base_dir / f"user_{owner_id}" / name
            project_dir.mkdir(parents=True, exist_ok=True)
            project = Project(owner=owner_id, name=name, tag=tag, path=str(project_dir))
            s.add(project)
            s.commit()
            return project.id

    def delete_project(self, owner_id, project_name: str):
        with self.Session() as s:
            project = s.query(Project).filter_by(owner=owner_id, name=project_name).first()
            if not project:
                raise ValueError("Project not found")
            try:
                path = Path(str(project.path))
                shutil.rmtree(path)
            except FileNotFoundError:
                pass
            s.delete(project)
            s.commit()

    def upload_zip(self, project_id: int, zip_path: str):
        with self.Session() as s:
            project = s.get(Project, project_id)
            if not project:
                raise ValueError("Project not found")
            path = Path(str(project.path))
            project_dir = Path(path)
            for item in project_dir.iterdir():
                if item.is_file(): item.unlink()
                elif item.is_dir(): shutil.rmtree(item)
            # Extract new files
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(project_dir)

            project.updated_at = datetime.now()
            s.commit()

    def get_project(self, project_name: str):
        with self.Session() as s:
            return s.query(Project).filter_by(name=project_name).first()

    def get_projects(self, owner_id: int):
        with self.Session() as s:
            return s.query(Project).filter_by(owner=owner_id).all()

    def search_projects(self, owner_id: int, tag: str = None):
        with self.Session() as s:
            return s.query(Project).filter_by(owner=owner_id, tag=tag).all()

if __name__ == "__main__":
    um = UserManager()
    pm = ProjectManager()
    try:
        owner = um.create_user("abc", "123")
    except ValueError:
        owner = um.verify_jwt(um.authenticate("abc", "123"))
    pid = pm.create_project(owner, "myproj", tag="v1")
    pm.upload_zip(pid, "project.zip")
    print([(p.name, p.updated_at) for p in pm.get_projects(owner)])
