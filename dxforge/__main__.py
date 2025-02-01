import argparse

from dxforge import Forge
from dxforge.ui import WebUI


def main():
    parser = argparse.ArgumentParser(
        description="Run the Divergex Forge service."
    )

    parser.add_argument(
        "project_name", type=str, help="Name of the project."
    )
    parser.add_argument(
        "project_dir", type=str, help="Path to the project directory."
    )
    parser.add_argument(
        "service_id", type=str, help="Unique identifier for the service."
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Host address (default: 127.0.0.1)."
    )
    parser.add_argument(
        "--port", type=int, default=7200, help="Port to run on (default: 7200)."
    )

    args = parser.parse_args()

    forge = Forge(
        project_name=args.project_name,
        project_dir=args.project_dir,
        service_id=args.service_id,
        host=args.host,
        port=args.port,
    )
    web_ui = WebUI()
    web_ui.register_routes(forge)
    forge.run()


if __name__ == "__main__":
    main()
