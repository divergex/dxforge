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


def main():
    orchestrator = Orchestrator()

# Example Usage
if __name__ == "__main__":
    main()
