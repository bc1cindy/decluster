"""Union-find with optional pre-seeding: UF(items) seeds singletons (so groups() includes untouched
nodes); UF() is lazy (unknown nodes added on first find/union)."""

class UF:
    def __init__(self, items=()):
        self.p = {x: x for x in items}
    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x
    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)
    def group(self, x):
        r = self.find(x); return [y for y in self.p if self.find(y) == r]
    def groups(self):
        g = {}
        for x in self.p: g.setdefault(self.find(x), []).append(x)
        return list(g.values())
