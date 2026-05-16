"""Flow: OD demand + travel graph + spawn schedule -> new passengers -> archived journeys.

PassengerGenerator(tg: TravelGraph, sampler: DirectDemandSampler, rate_per_100: float, stdev: float, speed: float = 5.0, seconds_per_tick: int = 1) -> None manages stochastic spawning, passenger updates, and archive handoff.
update(self) -> None advances the schedule and lifecycle.
get_all_generated_journeys(self) -> list[list[DirEdge]] exposes every planned path for pheromone use.

Inputs: a TravelGraph, DirectDemandSampler, spawn rate, deviation, and walking speed in km/h. One update tick equals seconds_per_tick seconds.
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
    def __init__(self, tg: 'TravelGraph', sampler: 'DirectDemandSampler', rate_per_hour: float, stdev: float, speed: float = 5.0, seconds_per_tick: int = 1) -> None:
        if not tg:
            raise ValueError("[PASSENGER GENERATOR] TravelGraph cannot be None.")
        if not sampler:
            raise ValueError("[PASSENGER GENERATOR] DirectDemandSampler cannot be None.")
        if rate_per_hour < 0:
            raise ValueError("[PASSENGER GENERATOR] rate_per_hour cannot be negative.")

        self.id: str = f"PG{uuid4().hex}"
        self.tg: 'TravelGraph' = tg
        self.sampler: 'DirectDemandSampler' = sampler
        self.rate_per_hour: float = float(rate_per_hour)
        self.stdev: float = float(stdev)
        self.speed_kmh: float = float(speed)
        self.speed: float = self.speed_kmh
        self.seconds_per_tick: int = seconds_per_tick
        self.simulated_time: int = 0

        self.total_spawned: int = 0
        self.passengers: list[Passenger] = []
        self.new_passengers_this_tick: list[Passenger] = []
        self.archived_passengers: list[Passenger] = []
        
        self.tick_counter: int = 0
        self.spawn_schedule: list[int] = [0 for _ in range(100)]
        
        self._generate_schedule()

    def __str__(self) -> str:
        return f"PassengerGenerator({self.id}): active={len(self.passengers)}, archived={len(self.archived_passengers)}, tick={self.tick_counter}"

    def _generate_schedule(self) -> None:
        self.spawn_schedule = [0 for _ in range(100)]
        expected_per_100_ticks = (self.rate_per_hour / 3600.0) * (100.0 * self.seconds_per_tick)
        spawn_count = int(max(0, random.gauss(expected_per_100_ticks, self.stdev)))
        
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
                    spawn_time=self.simulated_time,
                    seconds_per_tick=self.seconds_per_tick
                )
                self.passengers.append(p)
                self.new_passengers_this_tick.append(p)
                self.total_spawned += 1

        active_passengers = []
        for p in self.passengers:
            p.update()
            
            if p.state == Passenger.DONE:
                if getattr(p, 'despawn_tick', None) is None:
                    p.despawn_tick = self.simulated_time
                self.archived_passengers.append(p)
            else:
                active_passengers.append(p)

        self.passengers[:] = active_passengers
        self.tick_counter += 1
        self.simulated_time += self.seconds_per_tick
        
    def get_all_generated_journeys(self) -> list[list['DirEdge']]:
        """Extracts the planned paths of all passengers for pheromone deposition."""
        all_passengers = self.passengers + self.archived_passengers
        return [p.journey for p in all_passengers]
