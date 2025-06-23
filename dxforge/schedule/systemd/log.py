import subprocess


def log_service(service_name, lines: int = 30) -> None:
    try:
        result = subprocess.run(
            ["journalctl", "-u", service_name, f"-n{lines}", "--no-pager"],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"Last {lines} log lines for '{service_name}':\n")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Failed to get logs for service '{service_name}':")
        print(e.stderr or e.output or str(e))


def status_service(service_name) -> None:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True
        )
    except Exception as e:
        print(f"Failed to run systemctl: {e}")
        return

    status = result.stdout.strip()
    retcode = result.returncode

    if retcode == 0:
        print(f"Service '{service_name}' is active (running).")
    elif retcode in (1, 3):
        print(f"Service '{service_name}' is inactive (not running).")
    elif retcode == 4:
        print(f"Service '{service_name}' does not exist or is unknown.")
    else:
        print(f"Service '{service_name}' returned unknown status '{status}' with exit code {retcode}.")
