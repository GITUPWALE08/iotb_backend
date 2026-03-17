# telemetry/indicators/registry.py
from collections import defaultdict, deque

class IndicatorRegistry:
    def __init__(self):
        self.indicators = {}
        self._sorted_execution_plan = []

    def register(self, indicator_class):
        inst = indicator_class()
        self.indicators[inst.name] = inst
        self._build_dag()
        return indicator_class

    def _build_dag(self):
        """Topological sort of indicators based on their dependencies."""
        in_degree = {name: 0 for name in self.indicators}
        graph = defaultdict(list)

        for name, inst in self.indicators.items():
            for dep in inst.dependencies:
                if dep in self.indicators:
                    graph[dep].append(name)
                    in_degree[name] += 1

        queue = deque([name for name in in_degree if in_degree[name] == 0])
        sorted_plan = []

        while queue:
            node = queue.popleft()
            sorted_plan.append(self.indicators[node])
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        self._sorted_execution_plan = sorted_plan

    def get_execution_plan(self):
        return self._sorted_execution_plan

registry = IndicatorRegistry()