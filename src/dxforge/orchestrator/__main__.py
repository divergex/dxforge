import argparse

from .orchestrator import Orchestrator


def remove(orchestrator, args):
    removed = orchestrator.remove(args.container_name)
    if removed:
        print("Container '{}' removed".format(args.container_name))

def run(orchestrator, args):
    name = orchestrator.run(args.config)
    if name:
        print("Container '{}' created".format(name))


def logs(orchestrator, args):
    logs = orchestrator.logs(args.container_name)
    if logs:
        print("Container '{}' logged".format(args.container_name))
        print(logs)

def main():
    orchestrator = Orchestrator()
    parser = argparse.ArgumentParser(description="CLI Utility")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: run
    run_parser = subparsers.add_parser("run", help="Run the orchestrator with config")
    run_parser.add_argument("config", type=str, help="Path to the configuration file")
    run_parser.add_argument("--name", type=str, help="Name of the user or task")
    run_parser.add_argument("--filename", type=str, help="Path to the file to process")
    run_parser.set_defaults(func=run)

    # Subcommand: logs
    logs_parser = subparsers.add_parser("logs", help="Show logs for container")
    logs_parser.add_argument("container_name", type=str, help="Name of the container")
    logs_parser.set_defaults(func=logs)

    # Subcommand: remove
    remove_parser = subparsers.add_parser("remove", help="Remove a container")
    remove_parser.add_argument("container_name", type=str, help="Name of the container")
    remove_parser.set_defaults(func=remove)

    args = parser.parse_args()
    args.func(orchestrator, args)


if __name__ == "__main__":
    main()
