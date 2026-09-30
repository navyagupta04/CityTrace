"""Road topology and shortest-path inference (no map services required)."""
from heapq import heappop, heappush
from .config import CAMERAS, ROADS, MAX_SPEED_KMH


class CameraGraph:
    def __init__(self):
        self.cameras = {c.id: c for c in CAMERAS}
        self.edges = {c: {} for c in self.cameras}
        for a, b, km, free in ROADS:
            self.edges[a][b] = self.edges[b][a] = (km, free)

    def shortest(self, start: str, end: str) -> tuple[float, list[str]]:
        """Return road distance and inclusive path using Dijkstra."""
        if start not in self.cameras or end not in self.cameras:
            raise ValueError('Unknown camera')
        queue = [(0.0, start, [start])]
        seen = set()
        while queue:
            distance, node, path = heappop(queue)
            if node == end:
                return distance, path
            if node in seen:
                continue
            seen.add(node)
            for neighbor, (km, _) in self.edges[node].items():
                if neighbor not in seen:
                    heappush(queue, (distance + km, neighbor, path + [neighbor]))
        return float('inf'), []

    def possible(self, a: str, b: str, seconds: float) -> bool:
        distance, _ = self.shortest(a, b)
        return distance == 0 or (seconds > 0 and distance * 3600 / seconds <= MAX_SPEED_KMH)
