from unittest.mock import MagicMock, patch
from dxforge.orchestrator import Orchestrator


def test_list_images():
    with patch("docker.from_env") as mock_docker:
        mock_client = mock_docker.return_value
        mock_client.images.list.return_value = [
            MagicMock(tags=["test_image:latest"]),
            MagicMock(tags=[])
        ]

        orchestrator = Orchestrator("test_project", "/tmp", "test_service")
        images = orchestrator.list_images()

        assert images == [["test_image:latest"]]
        mock_client.images.list.assert_called_once()


def test_build_image():
    with patch("docker.from_env") as mock_docker, patch("pathlib.Path.exists", return_value=True):
        mock_client = mock_docker.return_value
        mock_client.images.build.return_value = MagicMock()

        orchestrator = Orchestrator("test_project", "/tmp", "test_service")
        orchestrator.build_image("test_service", "test_tag")

        mock_client.images.build.assert_called_once()


def test_start_container():
    with patch("docker.from_env") as mock_docker:
        mock_client = mock_docker.return_value
        mock_client.images.get.return_value = MagicMock(id="image_id")
        mock_client.containers.run.return_value = MagicMock(name="test_container")

        orchestrator = Orchestrator("test_project", "/tmp", "test_service")
        container, identifier = orchestrator.start_container("test_strategy", 8080)

        assert container.name == "test_container"
        mock_client.containers.run.assert_called_once()


def test_stop_container():
    with patch("docker.from_env") as mock_docker:
        mock_client = mock_docker.return_value
        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container

        orchestrator = Orchestrator("test_project", "/tmp", "test_service")
        orchestrator.stop_container("test_strategy", "test_id")

        mock_container.stop.assert_called_once()
        mock_client.containers.get.assert_called_once()


def test_cleanup():
    with patch("docker.from_env") as mock_docker:
        mock_client = mock_docker.return_value
        mock_container = MagicMock(status="exited", name="test_project_test_container")
        mock_client.containers.list.return_value = [mock_container]

        orchestrator = Orchestrator("test_project", "/tmp", "test_service")
        orchestrator.cleanup()

        mock_container.remove.assert_called_once()
        mock_client.images.prune.assert_called_once()
