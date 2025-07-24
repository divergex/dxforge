import os
import yaml
import docker
import hashlib
from pathlib import Path

from docker.errors import NotFound

client = docker.from_env()
STATE_DIR = Path("./.state")
STATE_DIR.mkdir(exist_ok=True)


def load_config(path="run_config.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)


def hash_script_path(script_path):
    return hashlib.sha256(script_path.encode()).hexdigest()


def get_state_path(script_path):
    h = hash_script_path(script_path)
    return STATE_DIR / f"{h}.running"


def is_running(script_path):
    state_file = get_state_path(script_path)
    if not state_file.exists():
        return False
    try:
        container = client.containers.get(state_file.read_text().strip())
        return container.status in ("running", "created")
    except NotFound:
        state_file.unlink(missing_ok=True)
        return False


def write_log(container, log_path):
    with open(log_path, "ab") as f:
        for log in container.logs(stream=True, stdout=True, stderr=True):
            f.write(log)


def run(cfg):
    script_path = cfg["container"]["script"]
    container_name = f"runner_{hash_script_path(script_path)[:12]}"
    state_file = get_state_path(script_path)

    try:
        container = client.containers.get(container_name)
        if container.status == 'running':
            print(f"Script '{script_path}' is already running (container: {container.id}).")
            return container_name
        else:
            print(f"Starting existing container {container_name}...")
            container.start()
            state_file.write_text(container.id)
            return container_name
    except docker.errors.NotFound:
        script_dir = os.path.dirname(script_path)
        script_name = os.path.basename(script_path)

        container = client.containers.run(
            image=cfg["container"]["image"],
            command=["python3", f"/app/{script_name}"],
            volumes={
                script_dir: {"bind": "/app", "mode": "ro"}
            },
            detach=True,
            name=container_name,
        )

        state_file.write_text(container.id)
        print(f"Started new container {container_name} for script {script_path}")
        return container_name

if __name__ == "__main__":
    config = load_config("examples/wick/config.yaml")
    run(config)
