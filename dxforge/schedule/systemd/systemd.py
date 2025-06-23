import os
import subprocess
import argparse
import sys
from datetime import datetime

from .log import log_service, status_service
from .service_dir import SERVICE_DIR
from .create import create_service


def delete_service(service_name, service_dir=SERVICE_DIR):
    service_file = os.path.join(service_dir, f"{service_name}.service")

    if not os.path.exists(service_file):
        print(f"Error: Service {service_name} does not exist.")
        return

    subprocess.run(["systemctl", "stop", service_name], check=True)
    subprocess.run(["systemctl", "disable", service_name], check=True)
    os.remove(service_file)

    subprocess.run(["systemctl", "daemon-reload"], check=True)

    print(f"Service {service_name} deleted successfully!")


def create_action(args):
    if not args.exec_start:
        print("Error: --exec_start argument is required for creating a service.", file=sys.stderr)
        sys.exit(1)
    description = args.description or f"Custom service created on {datetime.now()}"
    create_service(args.service_name, description, args.exec_start, args.working_directory, args.schedule)

def edit_action(args):
    if not any([args.exec_start, args.description, args.working_directory]):
        print("Error: At least one of --exec_start, --description, or --working_directory must be specified for editing.", file=sys.stderr)
        sys.exit(1)
    # Call your edit_service function (implement this)
    # edit_service(args.service_name, args.description, args.exec_start, args.working_directory)

def delete_action(args):
    delete_service(args.service_name)

def status_action(args):
    status_service(args.service_name)

def log_action(args):
    log_service(args.service_name)

def main():
    parser = argparse.ArgumentParser(description="Manage systemd services")

    parser.add_argument("action", choices=["create", "edit", "delete", "status", "log"],
                        help="Action to perform on systemd service")
    parser.add_argument("service_name", type=str,
                        help="The name of the systemd service (without .service extension)")

    parser.add_argument("--description", type=str, help="Description for the service")
    parser.add_argument("--exec_start", type=str, help="The command to start the service")
    parser.add_argument("--working_directory", type=str, help="Working directory for the service", default=os.getcwd())
    parser.add_argument("--schedule", type=str, help="Schedule to use for calling the service")

    args = parser.parse_args()

    action_map = {
        "create": create_action,
        "edit": edit_action,
        "delete": delete_action,
        "status": status_action,
        "log": log_action,
    }

    action_func = action_map.get(args.action)
    if not action_func:
        print(f"Unknown action: {args.action}", file=sys.stderr)
        sys.exit(1)

    action_func(args)

if __name__ == "__main__":
    main()