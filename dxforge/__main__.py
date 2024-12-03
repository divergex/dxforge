from dxlib.interfaces.services.http.fastapi import FastApiServer

from dxforge.orchestrator import Orchestrator

if __name__ == "__main__":
    orchestrator = Orchestrator("dxforge", "examples", "dxforge-1")

    server = FastApiServer(host="127.0.0.1", port=7200)
    server.register(orchestrator)

    try:
        server.run()
    except KeyboardInterrupt:
        pass
    finally:
        orchestrator.stop()

    # identifier1 = None
    # identifier2 = None
    #
    # try:
    #     orchestrator.build_image("strategy1")  # Build Docker image for strategy1
    #     container1, identifier1 = orchestrator.start_container("strategy1",
    #                                                            8001)  # Start instance 1 of strategy1 on port 8001
    #     container2, identifier2 = orchestrator.start_container("strategy1",
    #                                                            8002)  # Start instance 2 of strategy1 on port 8002
    # except KeyboardInterrupt:
    #     pass
    # finally:
    #     orchestrator.stop_container("strategy1", identifier1)  # Stop instance 1 of strategy1
    #     orchestrator.stop_container("strategy1", identifier2)  # Stop instance 2 of strategy1
    #     orchestrator.cleanup()  # Cleanup stopped containers
