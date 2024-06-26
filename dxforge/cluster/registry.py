from typing import Dict, List


class Registry:
    def __init__(self):
        self._registry: Dict[str, object] = {}
        self._tags: Dict[str, set] = {}

    def register(self, name, obj):
        self._registry[name] = obj

        # if obj has tags, add them to the tags registry
        if hasattr(obj, 'tags') and obj.tags:
            for tag in obj.tags:
                self._tags.setdefault(tag, set()).add(name)

    def get(self, name):
        return self._registry[name]

    def all(self) -> List[str]:
        return list(self._registry.keys())

    def find(self, tag) -> List[object]:
        return list(self._tags.get(tag, []))

    def find_all(self, tags) -> List[object]:
        return list(set.intersection(*[self._tags.get(tag, set()) for tag in tags]))

    def remove(self, name):
        del self._registry[name]

    def clear(self):
        for name in list(self._registry):
            self.remove(name)

    def __getitem__(self, name):
        return self.get(name)

    def __setitem__(self, name, obj):
        self.register(name, obj)

    def __contains__(self, name):
        return name in self._registry

    def __iter__(self):
        return iter(self._registry)

    def __len__(self):
        return len(self._registry)

    def __repr__(self):
        return f"<Registry: {self._registry}>"
