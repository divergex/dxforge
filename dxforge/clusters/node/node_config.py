from abc import ABC
from dataclasses import dataclass
from typing import List

import yaml


class Config(ABC):
    def __init__(self, *args, **kwargs):
        pass

    @classmethod
    def from_path(cls,
                  path: str = None):
        if path is None:
            return None
        config = yaml.safe_load(open(path, "r"))
        return cls(**config)


@dataclass
class NodeConfig(Config):
    @dataclass
    class BuildConfig(Config):
        def __init__(self,
                     tag: str,
                     dockerfile: str = None,
                     context: str = None,
                     depends_on: List[str] = None,
                     *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.tag = tag
            self.dockerfile = dockerfile
            self.context = context
            self.depends_on = depends_on if depends_on else []

    @dataclass
    class RunConfig(Config):
        def __init__(self,
                     ports: List[str] = None,
                     network: str = None,
                     *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._ports = ports
            self.network = network

        @property
        def ports(self):
            return {port.split(":")[0]: port.split(":")[1] if len(port.split(":")) > 1 else None for port in self._ports}

    build: BuildConfig
    run: RunConfig
    path: str = None
    info: dict = None

    @classmethod
    def from_config(cls,
                    config=None,
                    path: str = None,
                    info: dict = None):
        build_config = config.get("build")
        build = cls.BuildConfig(**config.get("build")) if build_config else None

        run_config = config.get("run")
        run = cls.RunConfig(**config.get("run")) if run_config else None

        return cls(build=build, run=run, path=path, info=info)
