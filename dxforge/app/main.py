from fastapi import FastAPI

from ..forge import Forge


class App(FastAPI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.forge = Forge("unix:///home/rzimmerdev/.docker/desktop/docker.sock")

        from .routes import router
        self.include_router(router)


app = App()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
