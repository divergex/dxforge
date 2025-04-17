import ast


class StrategyChecker(ast.NodeVisitor):
    def __init__(self):
        self.found = False
        self.import_aliases = {}

    def visit_ImportFrom(self, node):
        if node.module == "dxlib":
            for alias in node.names:
                self.import_aliases[alias.asname or alias.name] = f"dxlib.{alias.name}"

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name == "dxlib":
                self.import_aliases[alias.asname or "dxlib"] = "dxlib"

    def visit_ClassDef(self, node):
        for base in node.bases:
            # dxlib.Strategy directly
            if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
                if base.value.id in self.import_aliases and \
                        self.import_aliases[base.value.id] == "dxlib" and base.attr == "Strategy":
                    self.found = True
            # Strategy (imported via `from dxlib import Strategy`)
            elif isinstance(base, ast.Name):
                resolved = self.import_aliases.get(base.id)
                if resolved == "dxlib.Strategy":
                    self.found = True

    def implements_strategy(self, source: str) -> bool:
        tree = ast.parse(source)
        self.visit(tree)
        return self.found


if __name__ == "__main__":
    file = "strat.py"
    with open(file, "r") as f:
        code = f.read()

    checker = StrategyChecker()
    if not checker.implements_strategy(code):
        raise ValueError("Script must define a class inheriting from dxlib.Strategy")
