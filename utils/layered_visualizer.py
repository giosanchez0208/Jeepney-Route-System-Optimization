import numpy as np
import matplotlib.pyplot as plt
from city_graph import CityGraph
from directed_edge import DirEdge
from node import Node
from typing import Optional
from visualizer import StaticVisualizer

class LayeredVisualizer:
    def __init__(self, city_graph: CityGraph, journey: list[DirEdge], title: Optional[str] = None) -> None:
        self.cg = city_graph
        self.journey = journey
        self.title = title