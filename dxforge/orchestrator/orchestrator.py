from docker import from_env

from dxforge.orchestrator import logs, remove, run, stop
from dxforge.registry.mesh import MeshInterface


class SingletonMeta(type):
    """Metaclass for Singleton pattern."""
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(SingletonMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Orchestrator(metaclass=SingletonMeta):
    """Orchestrator class to manage service registrations and queries."""
    def __init__(self):
        self.interface = MeshInterface()
        self.client = from_env()
        self.logs = lambda name: logs.logs(self.client, name)
        self.remove = lambda name: remove.remove(self.client, name)
        self.stop = lambda name: stop.stop(self.client, name)

    def run(self, config):
        config = run.load_config(config)
        return run.run(config)
