import boto3
from dotenv import load_dotenv


class Manager:
    def __init__(self, endpoint_url: str, access_key: str, secret_key: str, bucket: str):
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket

        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )

        self._ensure_bucket()

    def _ensure_bucket(self):
        buckets = self.client.list_buckets()
        if self.bucket not in [b["Name"] for b in buckets["Buckets"]]:
            self.client.create_bucket(Bucket=self.bucket)

    def upload(self, key: str, file_path: str):
        self.client.upload_file(file_path, self.bucket, key)

    def download(self, key: str, output_path: str):
        self.client.download_file(self.bucket, key, output_path)



if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

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

    # Example usage
    manager.upload("forge", "forge.png")
    manager.download("forge", "forge2.png")
