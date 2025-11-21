import os
import tempfile
import zipfile
from pathlib import Path
from typing import Optional
import boto3


class Storage:
    """
    Handles project file storage in S3/MinIO with support for temporary local clones.
    """
    def __init__(
        self,
        bucket_name: str,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        region_name: Optional[str] = None,
    ):
        self.bucket_name = bucket_name
        self.s3 = boto3.resource(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region_name,
        )
        # ensure bucket exists
        if not self._bucket_exists(bucket_name):
            self.s3.create_bucket(Bucket=bucket_name)
        self.bucket = self.s3.Bucket(bucket_name)

    def _bucket_exists(self, bucket_name: str) -> bool:
        try:
            self.s3.meta.client.head_bucket(Bucket=bucket_name)
            return True
        except Exception:
            return False

    def upload_dir(self, dir_path: str, storage_path: str) -> None:
        """
        Upload all files from a local directory to the project path in S3/MinIO.
        """
        source_path = Path(dir_path)
        if not source_path.is_dir():
            raise ValueError(f"{source_path} is not a directory")

        for root, _, files in os.walk(source_path):
            for file in files:
                local_path = Path(root) / file
                relative_path = local_path.relative_to(source_path)
                s3_path = f"{storage_path}/{relative_path.as_posix()}"
                self.bucket.upload_file(str(local_path), s3_path)

    def upload_zip(self, zip_path: str, storage_path: str) -> None:
        """
        Extract a ZIP file into a temporary directory and upload its contents
        to the project path in S3/MinIO.
        """
        source_path = Path(zip_path)
        if not source_path.is_file():
            raise ValueError(f"{source_path} is not a file")

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)

            with zipfile.ZipFile(source_path, "r") as z:
                z.extractall(tmp)

            self.upload_dir(str(tmp), storage_path)

    def download_to_tempdir(self, host_path: str) -> str:
        """
        Download all files of a project into a temporary directory.
        Returns the path to the temp directory.
        """
        temp_dir = tempfile.mkdtemp()
        prefix = f"{host_path}/"

        for obj in self.bucket.objects.filter(Prefix=prefix):
            rel_path = Path(obj.key[len(prefix):])
            local_path = Path(temp_dir) / rel_path
            local_path.parent.mkdir(parents=True, exist_ok=True)
            self.bucket.download_file(obj.key, str(local_path))

        return temp_dir

    def delete_project(self, storage_path: str) -> None:
        """
        Delete all objects for a project.
        """
        prefix = f"{storage_path}/"
        objs = self.bucket.objects.filter(Prefix=prefix)
        objs.delete()

    def list_files(self, storage_path: str):
        """
        List all files under a project.
        """
        prefix = f"{storage_path}/"
        return [obj.key[len(prefix):] for obj in self.bucket.objects.filter(Prefix=prefix)]
