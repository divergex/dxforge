import websocket

import dxlib as dx
from websocket import WebSocketException


def on_message(ws, message):
    print("Received Message:", message)


def on_error(ws, error):
    print("Error:", error)


def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed")


def on_open(ws):
    pass


def main():
    portfolio = dx.Portfolio().add_cash(1e4)
    ws_url = "wss://localhost:6001/portfolio"  # replace with your WebSocket URL
    try:
        ws = websocket.WebSocketApp(ws_url,
                                    on_message=on_message,
                                    on_error=on_error,
                                    on_close=on_close)

        ws.send(portfolio.current_weights)
    except WebSocketException as e:
        print(e)


if __name__ == "__main__":
    main()
