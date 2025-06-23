import os
import subprocess

from dxforge.service.systemd import SERVICE_DIR


def service(service_name, description, exec_start, working_directory):
    working_directory = os.path.abspath(working_directory)
    exec_start = os.path.abspath(exec_start)

    return f"""[Unit]
Description={description}
After=network.target

[Service]
ExecStart={exec_start}
WorkingDirectory={working_directory}
Restart=on-failure
User=rzimmerdev
Environment="PATH=/sbin:/bin:/usr/sbin:/usr/bin"

StandardOutput=append:/var/log/{service_name}.log
StandardError=append:/var/log/{service_name}.err

[Install]
WantedBy=multi-user.target
"""


def timer(service_name, schedule):
    return f"""[Unit]
Description=Run {service_name} on service

[Timer]
OnCalendar={schedule}  # For example: OnCalendar=*-*-* 03:00:00

[Install]
WantedBy=timers.target
"""


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

    service_content = service(service_name, description, exec_start, working_directory)
    with open(service_file, 'w') as f:
        f.write(service_content)

    if schedule:
        timer_content = timer(service_name, schedule)
        with open(timer_file, 'w') as f:
            f.write(timer_content)

        print(f"Timer for {service_name} created with service {schedule}")

    subprocess.run(["systemctl", "daemon-reload"], check=True)
    if schedule:
        subprocess.run(["systemctl", "start", f"{service_name}.timer"], check=True)

    print(f"Service {service_name} created successfully!")
    if schedule:
        print(f"Service {service_name} will run based on the timer service.")
