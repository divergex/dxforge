import json
import time
from typing import AsyncGenerator

import pandas as pd
import websockets
import yaml

import dxlib as dx

"""
def connect():
    environment = request.form['environment']
    jwt = request.form['jwt']
    start_websocket(environment, jwt)
    return 'WebSocket connected!'

def start_websocket(environment, jwt):
    def on_message(ws, message):
        data = json.loads(message)
        ticker = data['ticker'].lower()
        last_price = data['last_price']
        time = data['time']
        update_quotation(ticker, last_price, time)

    ws = websocket.WebSocket()
    ws.connect(environment)

    ws.send('auth:' + jwt)

    while True:
        result = ws.recv()
        on_message(ws, result)
"""


class RBApi(dx.external.MarketApi):
    def __init__(self, tickers=None, environment="wss://testing.robobanker.com.br/ws/quotation", jwt="JWT"):
        super().__init__()
        self.interval = 1
        self.tickers = tickers if tickers is not None else ["petr4", "vale3"]

        self.environment = environment
        self.jwt = jwt

        self._remote_ws = None
        self.security_manager = dx.SecurityManager.from_list(self.tickers)

    def on_message(self, data):
        ticker = self.security_manager.get(data['ticker'])
        last_price = data['last_price']
        time = pd.Timestamp(data['time'])

        # multiindex dataframe
        df = pd.DataFrame({
            "price": last_price
        }, index=pd.MultiIndex.from_tuples([(ticker, time)], names=["security", "date"]))

        history = dx.History(
            df,
            schema=dx.Schema(
                levels=[dx.SchemaLevel.SECURITY, dx.SchemaLevel.DATE],
                fields=["price"],
                security_manager=self.security_manager
            )
        )

        return history

    async def quote_stream(self, *args, **kwargs) -> AsyncGenerator:
        async with websockets.connect(self.environment) as ws:
            self._remote_ws = ws

            await ws.send('auth:' + self.jwt)
            response = json.loads(await ws.recv())

            if response['status'] != "authorized client":
                raise Exception("Authentication failed")

            # send tickers as petr4, vale3, winv23, viia3, irbr3, rail3
            ticker_str = ", ".join(self.tickers)  # remove last comma
            ticker_str = ticker_str[:-2]
            await ws.send(ticker_str)

            while True:
                result = json.loads(await ws.recv())
                if result == "ping":
                    await ws.send("pong")
                    continue
                if result.get("ticker") == "":
                    continue
                yield self.on_message(result)


def main():
    interfaces = yaml.safe_load(open("info.yaml", "r"))["interfaces"]
    websocket_port = int(interfaces["MarketInterface"]["ws"]["port"])

    logger = dx.InfoLogger()
    interface = dx.internal.MarketInterface(RBApi())
    websocket_server = dx.servers.WebsocketServer(host="0.0.0.0", port=websocket_port, logger=logger)

    websocket_server.add_interface(interface)

    try:
        websocket_server.start()

        while not websocket_server.alive:
            time.sleep(1)

        websocket_server.listen(interface.quote_stream)

        while websocket_server.alive:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        websocket_server.stop()


if __name__ == "__main__":
    main()
