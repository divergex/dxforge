import docker
from docker.errors import NotFound
import logging
from dotenv import load_dotenv
import os

class MinIO:
    def __init__(self, image_tag: str = 'minio/minio:latest', container_name: str = 'minio', env_file: str = '.env'):
        self.client = docker.from_env()  # Initialize Docker client
        self.image_tag = image_tag
        self.container_name = container_name
        self.logger = logging.getLogger(__name__)

        # Load environment variables from the .env file
        load_dotenv(dotenv_path=env_file)

        # Access keys and storage path from environment variables
        self.access_key = os.getenv('MINIO_ACCESS_KEY')
        self.secret_key = os.getenv('MINIO_SECRET_KEY')
        self.storage_path = os.getenv('MINIO_STORAGE_PATH')
        self.storage_path = os.path.abspath(self.storage_path) if self.storage_path else None

        if not self.access_key or not self.secret_key or not self.storage_path:
            raise ValueError("MINIO_ACCESS_KEY, MINIO_SECRET_KEY, or MINIO_STORAGE_PATH not found in .env file")

    def _is_container_running(self):
        """Check if the MinIO container is running."""
        try:
            container = self.client.containers.get(self.container_name)
            return container.status == 'running'
        except NotFound:
            return False

    def start(self):
        """Start the MinIO container."""
        if self._is_container_running():
            self.logger.info(f"MinIO container {self.container_name} is already running.")
            return

        try:
            self.client.containers.run(
                self.image_tag,
                name=self.container_name,
                ports={"9000/tcp": 9000},
                environment={
                    "MINIO_ACCESS_KEY": self.access_key,
                    "MINIO_SECRET_KEY": self.secret_key
                },
                volumes={self.storage_path: {"bind": "/data", "mode": "rw"}},
                command="server /data",
            )
            self.logger.info(f"MinIO container {self.container_name} started successfully.")
        except Exception as e:
            self.logger.error(f"Failed to start MinIO container: {e}")

    def stop(self):
        """Stop the MinIO container."""
        try:
            container = self.client.containers.get(self.container_name)
            container.stop()
            self.logger.info(f"MinIO container {self.container_name} stopped.")
        except NotFound:
            self.logger.warning(f"MinIO container {self.container_name} not found.")
        except Exception as e:
            self.logger.error(f"Failed to stop MinIO container: {e}")

    def restart(self):
        """Restart the MinIO container."""
        try:
            container = self.client.containers.get(self.container_name)
            container.restart()
            self.logger.info(f"MinIO container {self.container_name} restarted.")
        except NotFound:
            self.logger.warning(f"MinIO container {self.container_name} not found.")
        except Exception as e:
            self.logger.error(f"Failed to restart MinIO container: {e}")

    def remove(self):
        """Remove the MinIO container."""
        try:
            container = self.client.containers.get(self.container_name)
            container.remove()
            self.logger.info(f"MinIO container {self.container_name} removed.")
        except NotFound:
            self.logger.warning(f"MinIO container {self.container_name} not found.")
        except Exception as e:
            self.logger.error(f"Failed to remove MinIO container: {e}")

    def __del__(self):
        """Ensure that the MinIO container is stopped before shutting down."""
        try:
            self.stop()
            self.logger.info(f"MinIOManager object for {self.container_name} is being deleted, stopping container.")
        except Exception as e:
            self.logger.error(f"Error stopping MinIO container in __del__: {e}")


if __name__ == "__main__":
    minio = MinIO()

    try:
        minio.start()
    except KeyboardInterrupt:
        minio.stop()
        print("MinIO container stopped.")
    except Exception as e:
        minio.stop()
        print(f"An error occurred: {e}")

