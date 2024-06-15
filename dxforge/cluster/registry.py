class Registry:
    def __init__(self):
        self._registry = {}

    def register(self, name, obj):
        self._registry[name] = obj

    def get(self, name):
        return self._registry[name]

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
