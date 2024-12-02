import signal
import sys
from dataclasses import dataclass
from datetime import datetime

from dxlib.interfaces import Service, TradingInterface
from dxlib.interfaces.services import Server, HttpEndpoint, Protocols
from dxlib.interfaces.services.http.fastapi import FastApiServer
from dxlib.interfaces.external.ibkr.ibkr import Ibkr

from dxforge.registry.mesh import MeshInterface


@dataclass
class HistoricalModel:
    symbols: list[str]
    start: datetime
    end: datetime
    interval: str


class Ibkrfeed(Service, TradingInterface):
    def __init__(self, name, service_id, tags):
        Service.__init__(self, name, service_id, tags)
        self.api = Ibkr("localhost", 4002, 0)

    @HttpEndpoint.post("/historical")
    def get_historical(self, model: HistoricalModel) -> str:
        history = self.api.market_interface.historical(model.symbols, model.start, model.end, model.interval)
        return history.__json__()


if __name__ == "__main__":
    mesh_interface = MeshInterface()
    mesh_interface.register(Server(host="127.0.0.1", port=7000, protocol=Protocols.HTTP))

    service = Ibkrfeed("Feed", "ibkr-feed-1", tags=["historical"])
    mesh_interface.register_service(service.to_model())
    server = FastApiServer(host="127.0.0.1", port=5001)
    server.register(service)

    service.api.start()

    def shutdown_handler(signum, frame):
        service.api.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)

    if __name__ == "__main__":
        try:
            server.run()
        except Exception as e:
            print(e)
            sys.exit(1)
