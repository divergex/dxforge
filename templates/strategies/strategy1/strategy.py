import signal
import sys
import threading
import time
from datetime import datetime

from starlette.middleware.cors import CORSMiddleware

from dxlib import History
from dxlib.interfaces.external.yfinance.yfinance import YFinance
from dxlib.interfaces import Service, HttpEndpoint, Server, Protocols
from dxlib.interfaces.internal import MeshInterface, MarketInterfaceInternal
from dxlib.interfaces.services.http.fastapi import FastApiServer


def run():
    market_api = YFinance()
    storage = "market_data"

    symbols = ["AAPL", "MSFT", "PETR4.SA", "BBAS3.SA"]
    start = datetime.datetime(2021, 1, 1)
    end = datetime.datetime(2024, 12, 31)


    strategy = ss.SignalStrategy(ss.custom.Rsi())
    executor = Executor(strategy)
    print("Executor")
    benchmark = Benchmark()
    benchmark.record("execute")
    print(executor.run(history, ss.views.SecuritySignalView))


class Executor(Service):
    def __init__(self, name, service_id, tags=None):
        super().__init__(name, service_id, tags)
        self.strategy = RsiStrategy()
        self.server = FastApiServer(host="0.0.0.0", port=5000)
        self.server.register(self)

        origins = [
            "http://localhost",
            "http://localhost:4200",  # Example: Frontend running on localhost
        ]

        # noinspection PyTypeChecker
        self.server.app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

        self.mesh_interface = MeshInterface()
        self.mesh_interface.register(Server(host="127.0.0.1", port=7000, protocol=Protocols.HTTP))
        self.mesh_interface.register_service(self.to_model())

        self.market_interface = MarketInterfaceInternal()
        self.market_interface.register(Server(host="127.0.0.1", port=5001, protocol=Protocols.HTTP))

        self.t = None
        # use thread safe variable from threading set
        self.running = threading.Event()
        self._timer = 0
        self._cooldown = 10

        self.data = {
            "signals": 0.0,
        }

    def __call__(self, *args, **kwargs):
        return self.strategy.execute(*args, **kwargs)

    def postback(self, observation: History):
        signals = self(observation)
        np_metrics = observation.data.values[-1]

        self.data["signals"] = signals
        self.data["metrics"] = np_metrics.tolist()

    @HttpEndpoint.get("/rsi")
    def data(self) -> dict:
        return self.data

    @HttpEndpoint.post("/rsi/stop")
    def _stop(self) -> bool:
        return self.stop()

    @HttpEndpoint.post("/rsi/start")
    def _start(self):
        self.run()
        return True

    @HttpEndpoint.get("/rsi/status")
    def status(self) -> bool:
        return self.running.is_set()

    def timer(self):
        while self.running.is_set() and self._timer < self._cooldown:
            time.sleep(.1)
            self._timer += .1

    def _run(self):
        try:
            while self.running.is_set():
                observation = self.market_interface.historical(
                    ["AAPL"],
                    datetime(2021, 1, 1),
                    datetime(2021, 1, 2),
                    "D")
                self.postback(observation)
                self._timer = 0
                self.timer()
        except KeyboardInterrupt:
            sys.exit(0)
        except ConnectionError:
            print("Could to server ended.")
            sys.exit(0)

    def run(self):
        self.running.set()
        self.t = threading.Thread(target=self._run)
        self.t.start()
        return self.t

    def stop(self):
        self.running.clear()
        self.t.join()
        return True


if __name__ == "__main__":
    executor = Executor("RsiStrategy", "rsi-strategy-1")


    def shutdown_handler(signum, frame):
        executor.stop()


    signal.signal(signal.SIGINT, shutdown_handler)

    if __name__ == "__main__":
        executor.run()
        executor.server.run()
