import pytest
import mongomock
from dxforge.orchestrator.db import ContainerStore
from dxforge.orchestrator.db import MongoDB


@pytest.fixture
def mock_db_helper():
    """Provide a DBHelper using mongomock."""
    db_helper = MongoDB(db_name="test_db")
    client = mongomock.MongoClient()
    db_helper.db = client.get_database("test_db")
    return db_helper


@pytest.fixture
def container_store(mock_db_helper):
    store = ContainerStore(db_helper=mock_db_helper)
    return store


def test_create_and_get_container(container_store: ContainerStore):
    container_store.create_container("proj-1", "cont-1")

    container = container_store.get_container("proj-1", "cont-1", cached=False)
    assert container is not None
    assert container.project_id == "proj-1"
    assert container.container_id == "cont-1"
    assert container.status == "stopped"


def test_update_status(container_store: ContainerStore):
    container_store.create_container("proj-1", "cont-2")
    container_store.update_status("proj-1", "cont-2", "running")

    container = container_store.get_container("proj-1", "cont-2")
    assert container.status == "running"


def test_list_containers(container_store: ContainerStore):
    container_store.create_container("proj-1", "cont-4")
    container_store.create_container("proj-2", "cont-5")
    container_store.update_status("proj-1", "cont-4", "running")

    all_containers = container_store.list_containers()
    assert len(all_containers) == 2

    running = container_store.list_containers(status="running")
    assert len(running) == 1
    assert running[0].container_id == "cont-4"


def test_delete_container(container_store: ContainerStore):
    container_store.create_container("proj-1", "cont-6")
    container_store.delete_container("proj-1", "cont-6")

    container = container_store.get_container("proj-1", "cont-6")
    assert container is None


if __name__ == "__main__":
    # pytest entire file
    pytest.main(["-s", __file__])
