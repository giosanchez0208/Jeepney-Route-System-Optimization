from route import Route
from city_graph import CityGraph
from directed_edge import DirEdge, _getDistance, _stitch
from node import Node


class TravelGraph:
    def __init__(self, city_graph: CityGraph, route_system: list[Route]) -> None:
        self.travel_graph: list[DirEdge] = self._construct(route_system)


