import asyncio
from typing import AsyncGenerator

import requests
import yaml

import dxlib as dx
from dxlib.interfaces.internal import MarketInterface
from dxlib.strategies.custom_strategies import RsiStrategy


def main():
    info = yaml.safe_load(open("info.yaml", "r"))
    interfaces = info["interfaces"]
    http_port = int(interfaces["StrategyInterface"]["http"]["port"])

    external = info["external"]
    required = external["feeds"]["yahoo-finance"]

    host = info.get("host", "host.docker.internal")

    m_info = requests.get(f"http://{host}:8000/cluster/feeds/node/yahoo-finance").json()
    m_status = requests.get(f"http://{host}:8000/cluster/feeds/status/yahoo-finance").json()

    m_port = m_info["interfaces"][required]["http"]["port"]
    m_host = list(m_status["instances"].values())[0]

    strategy = RsiStrategy(field="price")
    market_interface = MarketInterface(host=m_host)

    logger = dx.InfoLogger()
    executor = dx.Executor(strategy)
    executor_interface = dx.internal.ExecutorInterface(executor)
    http_server = dx.servers.HTTPServer(host="0.0.0.0", port=http_port, logger=logger)
    http_server.add_interface(executor_interface)
    try:
        http_server.start()
        quotes = market_interface.listen(market_interface.quote_stream, port=m_port, retry=1)

        def get_first_element_sync(async_gen):
            async def fetch_first_element():
                async for item in async_gen:
                    return item

            loop = asyncio.get_event_loop()
            return loop, loop.run_until_complete(fetch_first_element())

        loop, history = get_first_element_sync(quotes)
        schema = history.schema

        async def bar_generator(history_quotes: AsyncGenerator):
            try:
                async for history_quote in history_quotes:
                    history_quote.schema = schema
                    for bar in history_quote:
                        yield bar
            except KeyboardInterrupt:
                raise

        signals: AsyncGenerator = executor.run(bar_generator(quotes), input_schema=schema)

        async def print_signals():
            async for signal in signals:
                print(signal)

        loop.run_until_complete(print_signals())

    except KeyboardInterrupt:
        pass
    finally:
        http_server.stop()
        logger.info("Stopping strategy...")


if __name__ == "__main__":
    main()
