import os
import shutil
import tempfile
from pathlib import Path

import boto3

from docker import DockerClient
from docker.models.images import Image
from dotenv import load_dotenv

from dxlib.network.services import Service

from dxforge.manager.checker import StrategyChecker


class Manager:
    def __init__(self, endpoint_url: str, access_key: str, secret_key: str, bucket: str):
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket

        self.default_dockerfile_path = "template/default/Dockerfile"
        self.default_main_path = "template/default/main.py"

        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )
        self.services = {}
        self.images = {}
        self._ensure_bucket()

    def _ensure_bucket(self):
        buckets = self.client.list_buckets()
        if self.bucket not in [b["Name"] for b in buckets["Buckets"]]:
            self.client.create_bucket(Bucket=self.bucket)

    def store(self, key: str, data: bytes):
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
        )

    def upload(self, key: str, source: str):
        checker = StrategyChecker()
        checker.implements_strategy(source)

        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=source,
        )

    def download(self, key: str, output_path: str):
        self.client.download_file(self.bucket, key, output_path)

    def package(self, key: str, docker_client: DockerClient, source: str = None) -> str:
        with tempfile.TemporaryDirectory() as tmpdir:
            strategy_path = Path(tmpdir) / "strategy.py"

            if source:
                with open(strategy_path, "w") as f:
                    f.write(source)
            else:
                self.download(key, str(strategy_path))

            shutil.copy(self.default_dockerfile_path, Path(tmpdir) / "Dockerfile")
            shutil.copy(self.default_main_path, Path(tmpdir) / "main.py")

            image_tag = f"strategy-{key.replace('/', '-').replace('.py', '')}"
            image: Image = docker_client.images.build(
                path=tmpdir,
                tag=image_tag,
                rm=True
            )[0]

            return image_tag

    def create(self, client, source, service_name, tags=None):
        service = Service(service_name, tags)
        tag = self.package(service_name, client, source)

        self.store(
            key=service_name,
            data=tag.encode("utf-8")
        )

        self.services[service_name] = service
        self.images[service_name] = tag

        return service


def create() -> Manager:
    load_dotenv()

    minio_access_key = os.getenv("MINIO_ACCESS_KEY")
    minio_secret_key = os.getenv("MINIO_SECRET_KEY")
    minio_bucket = os.getenv("MINIO_BUCKET")

    manager = Manager(
        endpoint_url="http://localhost:9000",
        access_key=minio_access_key,
        secret_key=minio_secret_key,
        bucket=minio_bucket,
    )
    return manager


if __name__ == "__main__":
    manager = create()

    # Example usage
    manager.upload("forge", "forge.png")
    manager.download("forge", "forge2.png")
