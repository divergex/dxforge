from urllib.parse import urlparse

from dxlib import Strategy, Executor, History
from dxlib.module_proxy import ModuleProxy
from dxlib.network.interfaces.internal.oms import OrderManagementInterface
from dxlib.network.servers import Server, Protocols
from dxlib.network.interfaces.internal import MeshInterface, MarketInterfaceInternal
from dxlib.orders import Order


def main(strategy_module: str, *args, **kwargs):
    mesh = MeshInterface()
    mesh.register(Server(host="127.0.0.1", port=7000, protocol=Protocols.HTTP))

    services = mesh.get_service("market_api")
    market_api = None
    for service in services:
        for route, methods in service.endpoints.items():
            if "/market" in route and "GET" in methods:
                market_api = (route, methods["GET"])
        if market_api:
            break

    route, methods = market_api
    url = urlparse(route).hostname
    port = urlparse(route).port
    protocol = urlparse(route).scheme
    api = MarketInterfaceInternal()
    api.register(Server(host=url, port=port, protocol=Protocols.from_string(protocol)))

    oms = OrderManagementInterface(Server("127.0.0.1", 5001))

    def handler(out: History):
        oms.send_order("AAPL", Order(1, 100, "BUY"))

    strategy = ModuleProxy(strategy_module)[Strategy]
    executor = Executor(strategy, handler)
    executor.run(api.stream(*args, **kwargs))


if __name__ == "__main__":
    # read symbols from env
    import os

    symbols = os.getenv("SYMBOLS")

    main("strategy", *symbols)