"""passenger_generator.py

PassengerGenerator(...) -> None coordinates the stochastic generation, updating, and archiving of passengers.
update(self) -> None steps the spawn schedule, generates new journeys, updates agent states, and archives completed entities.
"""

import random

from .passenger import Passenger
from .travel_graph import TravelGraph
from .od_generator import TrafficAwareODGenerator

class PassengerGenerator:
    def __init__(
        self, 
        tg: TravelGraph, 
        od_gen: TrafficAwareODGenerator, 
        rate_per_100: float, 
        stdev: float, 
        speed: float = 5.0
    ) -> None:
        self.tg = tg
        self.od_gen = od_gen
        self.rate_per_100 = rate_per_100
        self.stdev = stdev
        self.speed = speed
        
        self.passengers: list[Passenger] = []
        self.new_passengers_this_tick: list[Passenger] = []
        self.archived_passengers: list[Passenger] = []
        
        self.tick_counter: int = 0
        self.spawn_schedule: list[int] = []
        
        self._generate_schedule()

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
            points = self.od_gen.generate_origins(n_points=2)
            journey = self.tg.findShortestJourney(points[0], points[1])
            
            if journey:
                p = Passenger(
                    start_pos=(points[0].lat, points[0].lon), 
                    journey=journey, 
                    speed=self.speed,
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

        self.passengers = active_passengers
        self.tick_counter += 1