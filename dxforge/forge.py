import logging

from docker import DockerClient
from docker.errors import APIError

from .cluster.orchestrator import Orchestrator


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Forge(metaclass=Singleton):
    def __init__(self, docker_socket=None, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.docker_client = DockerClient(base_url=docker_socket or 'unix://var/run/docker.sock')
        self.orchestrator = Orchestrator(self.docker_client)

    def join_swarm(self, advertise_addr):
        self.logger.info("Joining swarm...")
        join_token = self.docker_client.swarm.attrs.get('JoinTokens', {}).get('Worker', None)
        try:
            self.docker_client.swarm.join(remote_addrs=[advertise_addr], join_token=join_token)
        except APIError:
            self.logger.warning("Swarm already joined. Exiting and rejoining swarm...")
            self.docker_client.swarm.leave(force=True)

            self.docker_client.swarm.join(remote_addrs=[advertise_addr], join_token=join_token)

    def register_swarm(self, advertise_addr):
        self.logger.info("Registering swarm...")
        try:
            self.docker_client.swarm.init(advertise_addr=advertise_addr)
        except APIError:
            self.logger.warning("Swarm already initialized. Continuing...")

    def unregister_swarm(self):
        self.logger.info("Unregistering swarm...")
        self.docker_client.swarm.leave(force=True)
        self.logger.info("Swarm unregistered.")
