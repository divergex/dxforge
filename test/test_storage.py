from orchestrator.storage import Storage


def test_project_storage():
    storage = Storage("dxforge-projects", "http://localhost:9000", "minio", "minio123")
    storage.upload_dir("examples/wick", "wick")
