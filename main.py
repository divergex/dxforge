import os

from dotenv import load_dotenv

import yaml
import uvicorn

from dxforge import App, Forge


def main() -> App:
    load_dotenv()
    config_file = os.getenv("CONFIG_FILE", "config.yaml")
    config = yaml.safe_load(open(config_file, "r"))
    forge = Forge.from_config(config)

    description = """
    The dxforge suite is aimed at small teams and large teams that plan on scaling, 
    reducing costs and maintenance of quantitative trading strategies.

    The framework focuses on managing different strategies, their instances, feeds and portfolios 
    via distributed and scalable nodes, without the need of managing them individually.
    """

    return App(
        forge,
        title="dxforge",
        description=description,
        summary="An API-based orchestration platform by DivergeX.",
        version="v0.1.0",
        # terms_of_service="http://example.com/terms/",
        # contact={
        #     "name": "Deadpoolio the Amazing",
        #     "url": "http://x-force.example.com/contact/",
        #     "email": "dp@x-force.example.com",
        # },
        license_info={
            "name": "Apache 2.0",
            "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
        },
    )


if __name__ == "__main__":
    app = main()

    host = os.getenv("HOST", None)
    port = int(os.getenv("PORT", 8000))

    try:
        uvicorn.run(app, host=host, port=port)
    except KeyboardInterrupt:
        pass
    finally:
        pass
else:
    app = main()
    __all__ = ["app"]


@app.on_event("shutdown")
async def shutdown_event():
    await app.forge.stop()
    print("Shutting down...")
