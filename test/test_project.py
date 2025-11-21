from unittest.mock import MagicMock

import pytest
import docker
import tempfile
import os
from dxforge.orchestrator import ProjectData, BuildData
from orchestrator import ProjectManager


@pytest.mark.integration
def test_builder_build_real_image():
    client = docker.from_env()

    with tempfile.TemporaryDirectory() as tmpdir:
        app_path = os.path.join(tmpdir, "app.py")
        with open(app_path, "w") as f:
            f.write('print("hello world")\n')

        build_data = BuildData(
            base_image="python:3.12-slim",
            entrypoint_cmd=["python", "app.py"],
            open_ports={"http": 8050},
            build_args={}
        )

        project = ProjectData(
            owner="test_owner",
            name="test_project",
            build_data=build_data,
            storage_path=tmpdir
        )

        mock_storage = MagicMock()
        mock_storage.download_to_tempdir.return_value = tmpdir

        mock_store = MagicMock()

        project_manager = ProjectManager(project)
        project_manager.setup(mock_storage, mock_store)

        image = project_manager.build(client)

        assert image is not None


if __name__ == "__main__":
    pytest.main(["-s", __file__])
