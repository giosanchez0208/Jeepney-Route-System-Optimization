"""passenger.py

Public API:
- Passenger(start_pos, journey, speed, spawn_tick=0) models a traveler moving
  through walking, waiting, riding, and done states.
- curr_lat and curr_lon expose the passenger's live position.
- update(), get_target_route_idx(), get_target_alight_node(),
  get_planned_ride_weight(), complete_ride(), and get_remaining_time() make up
  the external control/query surface.

Internal API:
- _walk() advances the walking state across walk edges.
- _edge_idx, _edge_progress, current_jeep, and the state-machine fields track
  private journey progress.
"""

from typing import Optional

from .node import Node
from .directed_edge import DirEdge
from .jeep import Jeep

class Passenger:
    def __init__(self, start_pos: tuple[float, float], journey: list[DirEdge], speed: float, spawn_tick: int = 0) -> None:
        self._lat = start_pos[0]
        self._lon = start_pos[1]
        self.journey = journey
        self.speed = speed
        
        self.state = "WALKING"  # WALKING, WAITING, RIDING, DONE
        self.wait_ticks = 0
        
        self._edge_idx = 0
        self._edge_progress = 0.0
        
        self.current_jeep: Optional[Jeep] = None
        
        # Metric Tracking
        self.spawn_tick = spawn_tick
        self.despawn_tick: Optional[int] = None
        self.total_path_cost = sum(getattr(edge, 'weight', edge.getLength()) for edge in self.journey)

    @property
    def curr_lat(self) -> float:
        if self.state == "RIDING" and self.current_jeep:
            return self.current_jeep.currPos[0]
        return self._lat

    @property
    def curr_lon(self) -> float:
        if self.state == "RIDING" and self.current_jeep:
            return self.current_jeep.currPos[1]
        return self._lon

    @curr_lat.setter
    def curr_lat(self, value: float) -> None:
        self._lat = value

    @curr_lon.setter
    def curr_lon(self, value: float) -> None:
        self._lon = value

    def update(self) -> None:
        if self.state in ("DONE", "RIDING"):
            return
            
        if self.state == "WAITING":
            self.wait_ticks += 1
            return
            
        if self._edge_idx >= len(self.journey):
            self.state = "DONE"
            return
            
        current_edge = self.journey[self._edge_idx]
        edge_id = current_edge.id
        
        if edge_id.startswith("WA"):
            self.state = "WAITING"
            self.curr_lat = current_edge.end.lat
            self.curr_lon = current_edge.end.lon
            self._edge_idx += 1
            return
            
        if edge_id.startswith(("AL", "TR", "DI")):
            self.curr_lat = current_edge.end.lat
            self.curr_lon = current_edge.end.lon
            self._edge_idx += 1
            return
            
        if edge_id.startswith(("SW", "EW")):
            self._walk()
            
    def _walk(self) -> None:
        distance_to_move = self.speed
        
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
        if self.state != "WAITING" or self._edge_idx >= len(self.journey):
            return None
        edge = self.journey[self._edge_idx]
        if edge.id.startswith("RI_R"):
            return int(edge.id.split("_")[1][1:])
        return None
        
    def get_target_alight_node(self) -> Optional[Node]:
        idx = self._edge_idx
        while idx < len(self.journey):
            edge = self.journey[idx]
            if edge.id.startswith(("AL", "TR")):
                return edge.start
            idx += 1
        return None
        
    def get_planned_ride_weight(self) -> float:
        weight = 0.0
        idx = self._edge_idx
        while idx < len(self.journey):
            edge = self.journey[idx]
            if edge.id.startswith("RI"):
                weight += getattr(edge, 'weight', edge.getLength())
            elif edge.id.startswith(("AL", "TR")):
                break
            idx += 1
        return weight
        
    def complete_ride(self) -> None:
        while self._edge_idx < len(self.journey):
            edge_id = self.journey[self._edge_idx].id
            self._edge_idx += 1
            if edge_id.startswith(("AL", "TR")):
                break

    def get_remaining_time(self) -> float:
        if self.state == "DONE" or self._edge_idx >= len(self.journey):
            return 0.0
            
        remaining_cost = 0.0
        for idx in range(self._edge_idx, len(self.journey)):
            edge = self.journey[idx]
            remaining_cost += getattr(edge, 'weight', edge.getLength())
            
        if self.state == "WALKING" and self._edge_idx < len(self.journey):
            current_edge = self.journey[self._edge_idx]
            edge_len = getattr(current_edge, 'weight', current_edge.getLength())
            if edge_len > 0:
                ratio = self._edge_progress / current_edge.getLength()
                remaining_cost -= (edge_len * ratio)
                
        return max(0.0, remaining_cost)
