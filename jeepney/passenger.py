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
from .directed_edge import DirEdge, EDGE_SW, EDGE_WA, EDGE_RI, EDGE_AL, EDGE_TR, EDGE_EW, EDGE_DI
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
        self._stepped_this_tick: bool = False  # double-step guard (reset by PassengerGenerator)
        
        self.current_jeep: Optional[Jeep] = None
        
        # Track metric using the corrected variable name
        self.spawn_tick: int = spawn_time
        self.despawn_tick: Optional[int] = None

        # Track opportunistic riding: expected vs actual boarded route
        self.expected_route_idx: Optional[int] = None  # The route they planned to board (from EIVM)
        self.boarded_route_idx: Optional[int] = None   # The route they actually boarded
        self.boarded_expected: bool = False            # True if they boarded their planned route
        self.took_alternative: bool = False            # True if they boarded a different route

        self._cost_prefix_sums: list[float] = [0.0] * (len(self.journey) + 1)
        self._target_alight_nodes: list[Optional[Node]] = [None] * len(self.journey)
        self._planned_ride_weights: list[float] = [0.0] * len(self.journey)
        self._target_route_indices: list[Optional[int]] = [None] * len(self.journey)
        
        running_cost = 0.0
        for i, edge in enumerate(self.journey):
            running_cost += getattr(edge, 'weight', edge._length)
            self._cost_prefix_sums[i + 1] = running_cost
            
            if edge._edge_type == EDGE_RI:
                try:
                    self._target_route_indices[i] = int(edge.id.split("_")[1][1:])
                except (IndexError, ValueError):
                    pass

        self.total_path_cost: float = running_cost
        
        last_alight = None
        current_ride_weight = 0.0
        for i in range(len(self.journey) - 1, -1, -1):
            edge = self.journey[i]
            if edge._edge_type in (EDGE_AL, EDGE_TR):
                last_alight = edge.start
                current_ride_weight = 0.0
            elif edge._edge_type == EDGE_RI:
                current_ride_weight += getattr(edge, 'weight', edge._length)
                
            self._target_alight_nodes[i] = last_alight
            self._planned_ride_weights[i] = current_ride_weight

    def __str__(self) -> str:
        return (
            f"Passenger({self.id}): pos=({self.curr_lat:.4f}, {self.curr_lon:.4f}), "
            f"state={Passenger._STATE_NAMES.get(self.state, 'UNKNOWN')}, speed={self.speed_kmph} km/h, progress={self._edge_idx}/{len(self.journey)} edges"
        )

    def __getstate__(self):
        state = self.__dict__.copy()
        # Ensure the attribute exists even if it wasn't there before
        if '_stepped_this_tick' not in state:
            state['_stepped_this_tick'] = False
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        # Ensure the attribute exists upon loading
        if '_stepped_this_tick' not in self.__dict__:
            self.__dict__['_stepped_this_tick'] = False

    @property
    def curr_lat(self) -> float:
        if self.state == Passenger.RIDING and self.current_jeep:
            return self.current_jeep.curr_pos[1]
        # Lazy interpolation for walking passengers
        if self.state == Passenger.WALKING and self._edge_idx < len(self.journey):
            current_edge = self.journey[self._edge_idx]
            if current_edge._length > 0 and self._edge_progress > 0:
                ratio = self._edge_progress / current_edge._length
                return current_edge.start.lat + ratio * (current_edge.end.lat - current_edge.start.lat)
        return self._lat

    @curr_lat.setter
    def curr_lat(self, value: float) -> None:
        if not isinstance(value, (int, float)):
            raise TypeError("[PASSENGER] lat must be numeric.")
        self._lat = float(value)

    @property
    def curr_lon(self) -> float:
        if self.state == Passenger.RIDING and self.current_jeep:
            return self.current_jeep.curr_pos[0]
        # Lazy interpolation for walking passengers
        if self.state == Passenger.WALKING and self._edge_idx < len(self.journey):
            current_edge = self.journey[self._edge_idx]
            if current_edge._length > 0 and self._edge_progress > 0:
                ratio = self._edge_progress / current_edge._length
                return current_edge.start.lon + ratio * (current_edge.end.lon - current_edge.start.lon)
        return self._lon

    @curr_lon.setter
    def curr_lon(self, value: float) -> None:
        if not isinstance(value, (int, float)):
            raise TypeError("[PASSENGER] lon must be numeric.")
        self._lon = float(value)

    def update(self) -> None:
        # Double-step guard: if we already advanced this tick, bail out.
        # PassengerGenerator.update() clears the flag at the tick boundary.
        if self._stepped_this_tick:
            return
        self._stepped_this_tick = True

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
        etype = current_edge._edge_type
        
        if etype == EDGE_WA:
            self.state = Passenger.WAITING
            self.curr_lat = current_edge.end.lat
            self.curr_lon = current_edge.end.lon
            self._edge_idx += 1
        elif etype == EDGE_TR:
            self.curr_lat = current_edge.end.lat
            self.curr_lon = current_edge.end.lon
            self._edge_idx += 1
            self.state = Passenger.WAITING
        elif etype == EDGE_RI:
            self.state = Passenger.WAITING
        elif etype in (EDGE_AL, EDGE_DI):
            self.curr_lat = current_edge.end.lat
            self.curr_lon = current_edge.end.lon
            self._edge_idx += 1
        elif etype in (EDGE_SW, EDGE_EW):
            self._walk()
            
    def _walk(self) -> None:
        distance_to_move = self.speed_kmph * _KMH_TO_METERS_PER_TICK * self.seconds_per_tick
        
        while distance_to_move > 0 and self._edge_idx < len(self.journey):
            current_edge = self.journey[self._edge_idx]
            if current_edge._edge_type not in (EDGE_SW, EDGE_EW):
                break
                
            edge_length = current_edge._length
            remaining_edge_dist = edge_length - self._edge_progress
            
            if distance_to_move >= remaining_edge_dist:
                distance_to_move -= remaining_edge_dist
                self._edge_progress = 0.0
                self._edge_idx += 1
                # Update base coordinates to the new node
                self._lat = current_edge.end.lat
                self._lon = current_edge.end.lon
            else:
                self._edge_progress += distance_to_move
                distance_to_move = 0.0

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
            edge = self.journey[self._edge_idx]
            self._edge_idx += 1
            if edge._edge_type in (EDGE_AL, EDGE_TR):
                break

    def get_remaining_time(self) -> float:
        if self.state == Passenger.DONE or self._edge_idx >= len(self.journey):
            return 0.0
            
        remaining_cost = self.total_path_cost - self._cost_prefix_sums[self._edge_idx]
            
        if self.state == Passenger.WALKING and self._edge_idx < len(self.journey):
            current_edge = self.journey[self._edge_idx]
            edge_len = current_edge._length
            if edge_len > 0:
                edge_weight = getattr(current_edge, 'weight', edge_len)
                ratio = self._edge_progress / edge_len
                remaining_cost -= (edge_weight * ratio)
                
        return max(0.0, remaining_cost)

    def draw(self, context: tuple[tuple[float, float], tuple[float, float]], image: Image.Image, size: int = 4) -> Image.Image:
        if image.width != image.height:
            raise ValueError("[PASSENGER] Visualization requires a square image.")

        # Do not draw passengers that are inside a jeep or finished
        if self.state == Passenger.RIDING or getattr(self, 'state', None) == getattr(Passenger, 'DONE', -1):
            return image

        tl_lon, tl_lat = context[0]
        br_lon, br_lat = context[1]

        lon_range = br_lon - tl_lon
        lat_range = tl_lat - br_lat

        if lon_range == 0 or lat_range == 0:
            return image

        x = image.width * (self.curr_lon - tl_lon) / lon_range
        y = image.height * (tl_lat - self.curr_lat) / lat_range

        if self.state == Passenger.WAITING:
            color = "gray"
        elif self.state == Passenger.WALKING:
            color = "blue"
        else:
            color = "white"

        draw = ImageDraw.Draw(image)
        draw.ellipse([(x - size, y - size), (x + size, y + size)], fill=color)
        
        return image