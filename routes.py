"""Teaching-only route graph. All nodes and risk weights are fictional."""
from heapq import heappush, heappop

# (start, end, distance_km, illustrative_risk_0_to_1)
EDGES = [
    ("المدرسة", "الميدان", 1.0, .85),
    ("الميدان", "المستشفى", 1.0, .70),
    ("المدرسة", "الحديقة", 1.5, .10),
    ("الحديقة", "المستشفى", 1.4, .10),
    ("المدرسة", "المكتبة", 2.4, .20),
    ("المكتبة", "المستشفى", 1.2, .30),
    ("الحديقة", "المكتبة", 1.2, .20),
    ("الميدان", "المكتبة", 1.3, .50),
]


def best_route(start="المدرسة", end="المستشفى", safety_weight=0.0):
    if start == end:
        return [start], 0.0, 0.0
    graph = {}
    for a, b, km, risk in EDGES:
        graph.setdefault(a, []).append((b, km, risk))
        graph.setdefault(b, []).append((a, km, risk))
    heap = [(0.0, start, [start], 0.0, 0.0)]
    visited = set()
    while heap:
        cost, node, path, distance, risk_distance = heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        if node == end:
            return path, round(distance, 2), round(risk_distance, 2)
        for neighbour, km, risk in graph.get(node, []):
            if neighbour not in visited:
                heappush(heap, (cost + km * (1 + safety_weight * risk), neighbour,
                                path + [neighbour], distance + km, risk_distance + km * risk))
    raise ValueError("No route between points")
