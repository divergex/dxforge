from dataclasses import dataclass
from typing import List, Any, Dict, Tuple, Set

from dxlib.interfaces.servers.http import HttpEndpoint
from dxlib.interfaces.servers.server import Service


@dataclass
class ServiceModel:
    name: str
    service_id: str
    endpoints: str
    tags: List[str]

    def to_dict(self):
        return {
            "service_id": self.service_id,
            "name": self.name,
            "endpoints": self.endpoints,
            "tags": self.tags
        }


@dataclass
class KeyValue:
    key: str
    value: Any


class MeshService(Service):
    def __init__(self, name, service_id):
        super().__init__(name, service_id)
        self.kv_store = {}
        self.services: Dict[str, Dict[str, ServiceModel]] = {}  # service name -> {service id -> instance}
        self.tagged: Dict[str, Set[Tuple[str, str]]] = {}  # tag -> set of (name, id)
        self.service_index: Dict[Tuple[str, str], ServiceModel] = {}

    @HttpEndpoint.post("services")
    def register_service(self, service: ServiceModel):
        if service.name not in self.services:
            self.services[service.name] = {}
        self.services[service.name][service.service_id] = service

        self.service_index[(service.name, service.service_id)] = service

        for tag in service.tags:
            if tag not in self.tagged:
                self.tagged[tag] = set()
            self.tagged[tag].add((service.name, service.service_id))
        return service

    @HttpEndpoint.get("services/search")
    def search_services(self, tag: str):
        """Search for service by tag."""
        result = [self.service_index[(name, service_id)] for name, service_id in self.tagged.get(tag, set())]
        if not result:
            raise Exception("No service found with the given tag")
        return result

    @HttpEndpoint.get("services/{name}")
    def get_services(self, name: str):
        """Get all instances of a service by name."""
        if name not in self.services:
            raise Exception("Service not found")
        return list(self.services.get(name, {}).values())

    @HttpEndpoint.delete("services/{name}/{id}")
    def deregister_service(self, name: str, service_id: str):
        """Deregister a service instance by name and ID."""
        if name in self.services and service_id in self.services[name]:
            service = self.services[name].pop(service_id)
            if not self.services[name]:
                del self.services[name]

            del self.service_index[(name, service_id)]

            for tag in service.tags:
                if tag in self.tagged:
                    self.tagged[tag].remove((name, service_id))
                    if not self.tagged[tag]:
                        del self.tagged[tag]

        return {"message": "Service deregistered successfully"}

    @HttpEndpoint.get("discovery/{name}")
    def discover_service(self, name: str):
        """Discover endpoints for a given service name."""
        if name not in self.services:
            raise Exception("Service not found")
        return list(self.services.get(name, {}).values())

    @HttpEndpoint.put("kv")
    def set_key_value(self, data: KeyValue):
        """Set a key-value pair."""
        self.kv_store[data.key] = data.value
        return data

    @HttpEndpoint.get("kv/{key}")
    def get_key_value(self, key: str):
        """Retrieve a value by key."""
        if key not in self.kv_store:
            raise Exception("Key not found")
        return self.kv_store[key]
