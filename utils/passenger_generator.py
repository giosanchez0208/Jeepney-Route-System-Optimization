"""Flow: OD demand + travel graph + spawn schedule -> new passengers -> archived journeys.

PassengerGenerator(tg: TravelGraph, sampler: DirectDemandSampler, rate_per_100: float, stdev: float, speed: float = 5.0) -> None manages stochastic spawning, passenger updates, and archive handoff.
update(self) -> None advances the schedule and lifecycle.
get_all_generated_journeys(self) -> list[list[DirEdge]] exposes every planned path for pheromone use.

Inputs: a TravelGraph, DirectDemandSampler, spawn rate, deviation, and walking speed in km/h. One update tick equals one second.
Outputs: active passengers, archived passengers, and generated journey lists.
Imported modules used: DirEdge, Passenger, TravelGraph, DirectDemandSampler, and random.
"""

from __future__ import annotations
import random
from uuid import uuid4
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .directed_edge import DirEdge
    from .travel_graph import TravelGraph
    from .direct_demand_sampler import DirectDemandSampler

from .passenger import Passenger

class PassengerGenerator:
    def __init__(
        self, 
        tg: 'TravelGraph', 
        sampler: 'DirectDemandSampler', 
        rate_per_100: float, 
        stdev: float, 
        speed: float = 5.0
    ) -> None:
        if not tg:
            raise ValueError("[PASSENGER GENERATOR] TravelGraph cannot be None.")
        if not sampler:
            raise ValueError("[PASSENGER GENERATOR] DirectDemandSampler cannot be None.")
        if rate_per_100 < 0:
            raise ValueError("[PASSENGER GENERATOR] rate_per_100 cannot be negative.")

        self.id: str = f"PG{uuid4().hex}"
        self.tg: 'TravelGraph' = tg
        self.sampler: 'DirectDemandSampler' = sampler
        self.rate_per_100: float = float(rate_per_100)
        self.stdev: float = float(stdev)
        self.speed_kmh: float = float(speed)
        self.speed: float = self.speed_kmh
        
        self.passengers: list[Passenger] = []
        self.new_passengers_this_tick: list[Passenger] = []
        self.archived_passengers: list[Passenger] = []
        
        self.tick_counter: int = 0
        self.spawn_schedule: list[int] = []
        
        self._generate_schedule()

    def __str__(self) -> str:
        return f"PassengerGenerator({self.id}): active={len(self.passengers)}, archived={len(self.archived_passengers)}, tick={self.tick_counter}"

    def _generate_schedule(self) -> None:
        """Calculates a randomized distribution of passenger spawns for the next 100 ticks."""
        spawn_count = int(max(0, random.gauss(self.rate_per_100, self.stdev)))
        self.spawn_schedule = [0] * 100
        
        for _ in range(spawn_count):
            self.spawn_schedule[random.randint(0, 99)] += 1

    def update(self) -> None:
        self.new_passengers_this_tick = []
        
        if self.tick_counter > 0 and self.tick_counter % 100 == 0:
            self._generate_schedule()
            
        spawns_now = self.spawn_schedule[self.tick_counter % 100]
        
        for _ in range(spawns_now):
            origin = self.sampler.get_point()
            dest = self.sampler.get_point()
            journey = self.tg.findShortestJourney(origin, dest)
            
            if journey:
                p = Passenger(
                    start_pos=(origin.lon, origin.lat), 
                    journey=journey, 
                    speed=self.speed_kmh,
                    spawn_tick=self.tick_counter
                )
                self.passengers.append(p)
                self.new_passengers_this_tick.append(p)

        active_passengers = []
        for p in self.passengers:
            p.update()
            
            if p.state == "DONE":
                if p.despawn_tick is None:
                    p.despawn_tick = self.tick_counter
                self.archived_passengers.append(p)
            else:
                active_passengers.append(p)

        self.passengers[:] = active_passengers
        self.tick_counter += 1
        
    def get_all_generated_journeys(self) -> list[list['DirEdge']]:
        """Extracts the planned paths of all passengers for pheromone deposition."""
        all_passengers = self.passengers + self.archived_passengers
        return [p.journey for p in all_passengers]
