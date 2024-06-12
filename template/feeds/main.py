import dxlib as dx


def main():
    strategy = dx.strategies.RsiStrategy()
    interface = dx.interfaces.internal.StrategyInterface(strategy)

    logger = dx.InfoLogger()
    server = dx.servers.HTTPServer(host="localhost", port=5000, logger=logger)
    server.add_interface(interface)

    server.start(threaded=False)


if __name__ == "__main__":
    main()
