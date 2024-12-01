from dxlib.interfaces.internal.history import HistoryHttpInterface
from dxlib.interfaces.servers.http.http import HttpServer


def main():
    interface = HistoryHttpInterface()
    server = HttpServer("localhost", 8000)
    interface.register(server)

    print(
        interface.get()
    )

if __name__ == "__main__":
    main()
