import mongomock
import pytest

from orchestrator.db import MongoDB, Store
from orchestrator.project import ProjectData, BuildData


@pytest.fixture
def mock_db_helper():
    """Provide a DBHelper using mongomock."""
    db_helper = MongoDB(db_name="test_db")
    client = mongomock.MongoClient()
    db_helper.db = client.get_database("test_db")
    return db_helper


@pytest.fixture
def project_store(mock_db_helper):
    store = Store(mock_db_helper, "projects")
    store.register_model(ProjectData.__name__, ProjectData)

    return store


def test_project_data(project_store: Store):
    # ==================
    # Store project data
    # ==================
    build_data = BuildData(
        base_image="ubuntu:latest",
        entrypoint_cmd=["python", "main.py"],
        open_ports={"tcp:8000": 8000},
    )
    project_data = ProjectData(
        name="my-project",
        owner="uuid1",
        build_data=build_data,
    )

    project_store.create("project", "proj-1", project_data)

    # =====================
    # Retrieve project data
    # =====================
    metadata = project_store.get("project", {"document_id": "proj-1"})
    print(metadata)

    # Update instance
    project_store.partial_update("project", {"build_data.open_ports": {"tcp:8001": 8000}}, {"document_id": "proj-1"})
    metadata2 = project_store.get("project", {"document_id": "proj-1"})
    assert dict(metadata2.build_data.open_ports) == {"tcp:8001": 8000}

    # List instances
    instances = project_store.list_documents("project")
    assert "proj-1" in instances


if __name__ == "__main__":
    pytest.main(["-s", __file__])
