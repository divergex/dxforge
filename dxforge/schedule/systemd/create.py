import os
import subprocess

from dxforge.schedule.systemd import SERVICE_DIR


def service(description, exec_start, working_directory):
    return """[Unit]
Description={0}
After=network.target

[Service]
ExecStart={1}
WorkingDirectory={2}
Restart=on-failure
User=root
Group=root
Environment="PATH=/sbin:/bin:/usr/sbin:/usr/bin"

[Install]
WantedBy=multi-user.target
""".format(description, exec_start, working_directory)


def timer(service_name, schedule):
    return """[Unit]
Description=Run {0} on schedule

[Timer]
OnCalendar={1}  # For example: OnCalendar=*-*-* 03:00:00

[Install]
WantedBy=timers.target
""".format(service_name, schedule)


def create_service(
        service_name,
        description,
        exec_start,
        working_directory="/",
        schedule=None,
        service_dir=SERVICE_DIR
):
    if not exec_start.startswith("/"):
        exec_start = os.path.abspath(exec_start)

    service_file = os.path.join(service_dir, f"{service_name}.service")
    timer_file = os.path.join(service_dir, f"{service_name}.timer")

    if os.path.exists(service_file):
        print(f"Error: Service {service_name} already exists.")
        return

    service_content = service(description, exec_start, working_directory)
    with open(service_file, 'w') as f:
        f.write(service_content)

    if schedule:
        timer_content = timer(service_name, schedule)
        with open(timer_file, 'w') as f:
            f.write(timer_content)

        print(f"Timer for {service_name} created with schedule {schedule}")

    subprocess.run(["systemctl", "daemon-reload"], check=True)
    if schedule:
        subprocess.run(["systemctl", "start", f"{service_name}.timer"], check=True)

    print(f"Service {service_name} created successfully!")
    if schedule:
        print(f"Service {service_name} will run based on the timer schedule.")
