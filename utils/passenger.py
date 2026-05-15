"""Flow: start position + journey + speed (km/h) -> passenger state machine -> walking, waiting, riding, done.

Passenger(start_pos: tuple[float, float], journey: list[DirEdge], speed: float, spawn_time: int = 0) -> None tracks live coordinates, state transitions, ride planning, and remaining travel time.
update(self) -> None advances the passenger state.
get_target_route_idx(self) -> Optional[int], get_target_alight_node(self) -> Optional[Node], get_planned_ride_weight(self) -> float, complete_ride(self) -> None, and get_remaining_time(self) -> float are the query/control methods.

Inputs: a start position, a DirEdge journey, movement speed in km/h, spawn time, and seconds per tick.
Outputs: updated passenger state plus route and timing queries.
Imported modules used: Node, DirEdge, Jeep, Optional, and PIL.Image.
"""
from __future__ import annotations
from uuid import uuid4
from typing import Optional
from PIL import Image, ImageDraw

from .node import Node
from .directed_edge import DirEdge
from .jeep import Jeep

_KMH_TO_METERS_PER_TICK: float = 1000.0 / 3600.0

class Passenger:
    WALKING = 0
    WAITING = 1
    RIDING = 2
    DONE = 3
    
    _STATE_NAMES = {
        WALKING: "WALKING",
        WAITING: "WAITING",
        RIDING: "RIDING",
        DONE: "DONE"
    }

    def __init__(self, start_pos: tuple[float, float], journey: list[DirEdge], speed: float, spawn_time: int = 0, seconds_per_tick: int = 1) -> None:
        if not isinstance(start_pos, tuple) or len(start_pos) != 2:
            raise TypeError("[PASSENGER] start_pos must be a tuple of (lon, lat).")
        if speed < 0:
            raise ValueError("[PASSENGER] speed cannot be negative.")
        if not journey:
            raise ValueError("[PASSENGER] journey cannot be empty.")
            
        self.id: str = f"P{uuid4().hex}"
        self._lon: float = float(start_pos[0])
        self._lat: float = float(start_pos[1])
        self.journey: list[DirEdge] = journey
        self.speed_kmph: float = float(speed)
        self.speed: float = self.speed_kmph
        self.seconds_per_tick: int = seconds_per_tick
        
        self.state: int = Passenger.WALKING  
        self.wait_ticks: int = 0
        
        self._edge_idx: int = 0
        self._edge_progress: float = 0.0
        
        self.current_jeep: Optional[Jeep] = None
        
        # Track metric using the corrected variable name
        self.spawn_tick: int = spawn_time
        self.despawn_tick: Optional[int] = None

        self._cost_prefix_sums: list[float] = [0.0] * (len(self.journey) + 1)
        self._target_alight_nodes: list[Optional[Node]] = [None] * len(self.journey)
        self._planned_ride_weights: list[float] = [0.0] * len(self.journey)
        self._target_route_indices: list[Optional[int]] = [None] * len(self.journey)
        
        running_cost = 0.0
        for i, edge in enumerate(self.journey):
            running_cost += getattr(edge, 'weight', edge.getLength())
            self._cost_prefix_sums[i + 1] = running_cost
            
            if edge.id.startswith("RI_R"):
                try:
                    self._target_route_indices[i] = int(edge.id.split("_")[1][1:])
                except (IndexError, ValueError):
                    pass

        self.total_path_cost: float = running_cost
        
        last_alight = None
        current_ride_weight = 0.0
        for i in range(len(self.journey) - 1, -1, -1):
            edge = self.journey[i]
            if edge.id.startswith(("AL", "TR")):
                last_alight = edge.start
                current_ride_weight = 0.0
            elif edge.id.startswith("RI"):
                current_ride_weight += getattr(edge, 'weight', edge.getLength())
                
            self._target_alight_nodes[i] = last_alight
            self._planned_ride_weights[i] = current_ride_weight

    def __str__(self) -> str:
        return (
            f"Passenger({self.id}): pos=({self.curr_lat:.4f}, {self.curr_lon:.4f}), "
            f"state={Passenger._STATE_NAMES.get(self.state, 'UNKNOWN')}, speed={self.speed_kmph} km/h, progress={self._edge_idx}/{len(self.journey)} edges"
        )

    @property
    def curr_lat(self) -> float:
        if self.state == Passenger.RIDING and self.current_jeep:
            return self.current_jeep.curr_pos[1]
        return self._lat

    @property
    def curr_lon(self) -> float:
        if self.state == Passenger.RIDING and self.current_jeep:
            return self.current_jeep.curr_pos[0]
        return self._lon

    @curr_lat.setter
    def curr_lat(self, value: float) -> None:
        if not isinstance(value, (int, float)):
            raise TypeError("[PASSENGER] lat must be numeric.")
        self._lat = float(value)

    @curr_lon.setter
    def curr_lon(self, value: float) -> None:
        if not isinstance(value, (int, float)):
            raise TypeError("[PASSENGER] lon must be numeric.")
        self._lon = float(value)

    def update(self) -> None:
        match self.state:
            case Passenger.DONE | Passenger.RIDING:
                return
            case Passenger.WAITING:
                self.wait_ticks += 1
                return

        if self._edge_idx >= len(self.journey):
            self.state = Passenger.DONE
            return
            
        current_edge = self.journey[self._edge_idx]
        edge_prefix = current_edge.id[:2]
        
        match edge_prefix:
            case "WA":
                self.state = Passenger.WAITING
                self.curr_lat = current_edge.end.lat
                self.curr_lon = current_edge.end.lon
                self._edge_idx += 1
            case "TR":
                self.curr_lat = current_edge.end.lat
                self.curr_lon = current_edge.end.lon
                self._edge_idx += 1
                self.state = Passenger.WAITING
            case "RI":
                self.state = Passenger.WAITING
            case "AL" | "DI":
                self.curr_lat = current_edge.end.lat
                self.curr_lon = current_edge.end.lon
                self._edge_idx += 1
            case "SW" | "EW":
                self._walk()
            
    def _walk(self) -> None:
        distance_to_move = self.speed_kmph * _KMH_TO_METERS_PER_TICK * self.seconds_per_tick
        
        while distance_to_move > 0 and self._edge_idx < len(self.journey):
            current_edge = self.journey[self._edge_idx]
            
            if not current_edge.id.startswith(("SW", "EW")):
                break
                
            edge_length = current_edge.getLength()
            remaining_edge_dist = edge_length - self._edge_progress
            
            if distance_to_move >= remaining_edge_dist:
                distance_to_move -= remaining_edge_dist
                self._edge_progress = 0.0
                self._edge_idx += 1
                self.curr_lat = current_edge.end.lat
                self.curr_lon = current_edge.end.lon
            else:
                self._edge_progress += distance_to_move
                distance_to_move = 0.0
                
                if edge_length > 0:
                    ratio = self._edge_progress / edge_length
                    self.curr_lat = current_edge.start.lat + ratio * (current_edge.end.lat - current_edge.start.lat)
                    self.curr_lon = current_edge.start.lon + ratio * (current_edge.end.lon - current_edge.start.lon)

    def get_target_route_idx(self) -> Optional[int]:
        if self.state != Passenger.WAITING or self._edge_idx >= len(self.journey):
            return None
        return self._target_route_indices[self._edge_idx]
        
    def get_target_alight_node(self) -> Optional[Node]:
        if self._edge_idx >= len(self.journey):
            return None
        return self._target_alight_nodes[self._edge_idx]
        
    def get_planned_ride_weight(self) -> float:
        if self._edge_idx >= len(self.journey):
            return 0.0
        return self._planned_ride_weights[self._edge_idx]
        
    def complete_ride(self) -> None:
        while self._edge_idx < len(self.journey):
            edge_id = self.journey[self._edge_idx].id
            self._edge_idx += 1
            if edge_id.startswith(("AL", "TR")):
                break

    def get_remaining_time(self) -> float:
        if self.state == Passenger.DONE or self._edge_idx >= len(self.journey):
            return 0.0
            
        remaining_cost = self.total_path_cost - self._cost_prefix_sums[self._edge_idx]
            
        if self.state == Passenger.WALKING and self._edge_idx < len(self.journey):
            current_edge = self.journey[self._edge_idx]
            edge_len = current_edge.getLength()
            if edge_len > 0:
                edge_weight = getattr(current_edge, 'weight', edge_len)
                ratio = self._edge_progress / edge_len
                remaining_cost -= (edge_weight * ratio)
                
        return max(0.0, remaining_cost)

    def draw(self, context: tuple[tuple[float, float], tuple[float, float]], image: Image.Image, size: int = 4) -> Image.Image:
        if image.width != image.height:
            raise ValueError("[PASSENGER] Visualization requires a square image.")

        if self.state == Passenger.RIDING:
            return image

        tl_lon, tl_lat = context[0]
        br_lon, br_lat = context[1]

        lon_range = br_lon - tl_lon
        lat_range = tl_lat - br_lat

        if lon_range == 0 or lat_range == 0:
            return image

        x = image.width * (self.curr_lon - tl_lon) / lon_range
        y = image.height * (tl_lat - self.curr_lat) / lat_range
        
        x = max(0, min(image.width - 1, int(x)))
        y = max(0, min(image.height - 1, int(y)))

        draw = ImageDraw.Draw(image)
        draw.rectangle([x - size/2, y - size/2, x + size/2, y + size/2], fill="blue")

        return image