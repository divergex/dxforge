import os
import subprocess
import argparse
from datetime import datetime

SYSTEMD_SERVICE_DIR = "/etc/systemd/system/"


def create_service(service_name, description, exec_start, schedule=None, working_directory=None):
    if not exec_start.startswith("/"):
        exec_start = os.path.abspath(exec_start)

    service_file = os.path.join(SYSTEMD_SERVICE_DIR, f"{service_name}.service")
    timer_file = os.path.join(SYSTEMD_SERVICE_DIR, f"{service_name}.timer")

    if os.path.exists(service_file):
        print(f"Error: Service {service_name} already exists.")
        return

    # Create the service content
    service_content = f"""[Unit]
Description={description}
After=network.target

[Service]
ExecStart={exec_start}
WorkingDirectory={working_directory if working_directory else "/"}
Restart=on-failure
User=root
Group=root
Environment="PATH=/sbin:/bin:/usr/sbin:/usr/bin"

[Install]
WantedBy=multi-user.target
"""

    # Write the service unit file
    with open(service_file, 'w') as f:
        f.write(service_content)

    if schedule:
        # Create the timer content
        timer_content = f"""[Unit]
Description=Run {service_name} on schedule

[Timer]
OnCalendar={schedule}  # For example: OnCalendar=*-*-* 03:00:00

[Install]
WantedBy=timers.target
"""
        # Write the timer unit file
        with open(timer_file, 'w') as f:
            f.write(timer_content)

        print(f"Timer for {service_name} created with schedule {schedule}")

    # Reload systemd configuration to apply new units
    subprocess.run(["systemctl", "daemon-reload"], check=True)

    # Enable the service and timer (if schedule is provided)
    subprocess.run(["systemctl", "enable", service_name], check=True)
    if schedule:
        subprocess.run(["systemctl", "enable", f"{service_name}.timer"], check=True)

    print(f"Service {service_name} created successfully!")
    if schedule:
        print(f"Service {service_name} will run based on the timer schedule.")


# def edit_service(service_name, new_exec_start=None, new_description=None, new_working_directory=None):
#     """Edit an existing systemd service file"""
#
#     service_file = os.path.join(SYSTEMD_SERVICE_DIR, f"{service_name}.service")
#
#     if not os.path.exists(service_file):
#         print(f"Error: Service {service_name} does not exist.")
#         return
#
#     with open(service_file, 'r') as f:
#         content = f.readlines()
#
#     for i, line in enumerate(content):
#         if new_exec_start and line.startswith("ExecStart="):
#             # If a new exec_start is provided, convert it to an absolute path and prepend the Python interpreter
#             if not new_exec_start.startswith("/"):
#                 new_exec_start = os.path.abspath(new_exec_start)
#             python_interpreter = sys.executable  # Use the Python interpreter that was used to run this script
#             new_exec_start = f"{python_interpreter} {new_exec_start}"
#             content[i] = f"ExecStart={new_exec_start}\n"
#         elif new_description and line.startswith("Description="):
#             content[i] = f"Description={new_description}\n"
#         elif new_working_directory and line.startswith("WorkingDirectory="):
#             content[i] = f"WorkingDirectory={new_working_directory}\n"
#
#     with open(service_file, 'w') as f:
#         f.writelines(content)
#
#     subprocess.run(["systemctl", "daemon-reload"], check=True)
#
#     print(f"Service {service_name} edited successfully!")


def delete_service(service_name):
    service_file = os.path.join(SYSTEMD_SERVICE_DIR, f"{service_name}.service")

    if not os.path.exists(service_file):
        print(f"Error: Service {service_name} does not exist.")
        return

    subprocess.run(["systemctl", "stop", service_name], check=True)
    subprocess.run(["systemctl", "disable", service_name], check=True)
    os.remove(service_file)

    subprocess.run(["systemctl", "daemon-reload"], check=True)

    print(f"Service {service_name} deleted successfully!")


def status_service(service_name):
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True, text=True, check=True
        )
        if result.stdout.strip() == "active":
            print(f"Service {service_name} is running.")
        else:
            print(f"Service {service_name} is not running.")
    except subprocess.CalledProcessError:
        print(f"Error: Service {service_name} is not found.")


def main():
    parser = argparse.ArgumentParser(description="Manage systemd services")

    parser.add_argument("action", choices=["create", "edit", "delete", "status"],
                        help="Action to perform on systemd service")
    parser.add_argument("service_name", type=str, help="The name of the systemd service (without .service extension)")

    parser.add_argument("--description", type=str, help="Description for the service")
    parser.add_argument("--exec_start", type=str, help="The command to start the service")
    parser.add_argument("--working_directory", type=str, help="Working directory for the service", default=os.getcwd())
    parser.add_argument("--schedule", type=str, help="Schedule to use for calling the service")

    args = parser.parse_args()

    if args.action == "create":
        if not args.exec_start:
            print("Error: --exec_start argument is required for creating a service.")
        else:
            description = args.description if args.description else f"Custom service created on {datetime.now()}"
            create_service(args.service_name, description, args.exec_start, args.working_directory, args.schedule)

    elif args.action == "edit":
        if not args.exec_start and not args.description and not args.working_directory:
            print(
                "Error: At least one of --exec_start, --description, or --working_directory must be specified for editing.")
        else:
            pass
            print("Nuh uh")
            # edit_service(args.service_name, args.exec_start, args.description, args.working_directory)

    elif args.action == "delete":
        delete_service(args.service_name)

    elif args.action == "status":
        status_service(args.service_name)


if __name__ == "__main__":
    main()
