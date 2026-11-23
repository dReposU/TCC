"""
Modelado espacial 3D del edificio universitario:
- 8 pisos (Piso 1 .. Piso 8)
- 4 aulas por piso (2 al norte y 2 al sur del pasillo central)
- 3 salidas de emergencia por piso (Oeste, Centro, Este)
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import random


@dataclass(frozen=True)
class RoomZone:
    name: str
    floor: int          # 0..7 (Piso 1..8)
    zone_type: str      # "AULA" | "PASILLO" | "SALIDA"
    center: Tuple[float, float, float]
    door_pos: Tuple[float, float, float]
    size: Tuple[float, float]


class UniversityBuilding:
    NUM_FLOORS = 8
    ROOMS_PER_FLOOR = 4
    EXITS_PER_FLOOR = 3
    FLOOR_HEIGHT = 4.6
    BUILDING_WIDTH = 36.0
    BUILDING_DEPTH = 16.0

    def __init__(self) -> None:
        self.floors_y: List[float] = [f * self.FLOOR_HEIGHT for f in range(self.NUM_FLOORS)]
        self.classrooms: Dict[int, List[RoomZone]] = {}
        self.corridors: Dict[int, RoomZone] = {}
        self.exits: Dict[int, List[RoomZone]] = {}
        self._build_layout()

    def _build_layout(self) -> None:
        for f in range(self.NUM_FLOORS):
            y = self.floors_y[f]
            self.corridors[f] = RoomZone(
                name=f"P{f+1}_Pasillo",
                floor=f,
                zone_type="PASILLO",
                center=(0.0, y, 0.0),
                door_pos=(0.0, y, 0.0),
                size=(34.0, 4.4),
            )

            room_specs = [
                ("Aula_1", -8.5, -5.1, -2.2),
                ("Aula_2",  8.5, -5.1, -2.2),
                ("Aula_3", -8.5,  5.1,  2.2),
                ("Aula_4",  8.5,  5.1,  2.2),
            ]
            self.classrooms[f] = [
                RoomZone(
                    name=f"P{f+1}_{r_name}",
                    floor=f,
                    zone_type="AULA",
                    center=(cx, y, cz),
                    door_pos=(cx, y, door_z),
                    size=(14.0, 5.4),
                )
                for r_name, cx, cz, door_z in room_specs
            ]

            exit_specs = [
                ("Salida_1", -17.2,  0.0),
                ("Salida_2",   0.0, -2.3),
                ("Salida_3",  17.2,  0.0),
            ]
            self.exits[f] = [
                RoomZone(
                    name=f"P{f+1}_{e_name}",
                    floor=f,
                    zone_type="SALIDA",
                    center=(ex, y, ez),
                    door_pos=(ex, y, ez),
                    size=(2.2, 2.2),
                )
                for e_name, ex, ez in exit_specs
            ]

    def sample_person_spawn(self) -> Tuple[int, List[float], str]:
        floor = random.randint(0, self.NUM_FLOORS - 1)
        y = self.floors_y[floor]
        if random.random() < 0.80:
            room = random.choice(self.classrooms[floor])
            x = room.center[0] + random.uniform(-5.2, 5.2)
            z = room.center[2] + random.uniform(-1.8, 1.8)
            return floor, [x, y, z], room.name
        x = random.uniform(-14.0, 14.0)
        z = random.uniform(-1.4, 1.4)
        return floor, [x, y, z], f"P{floor+1}_Pasillo"

    def sample_zombie_spawn(self) -> Tuple[int, List[float], str]:
        floor = random.randint(0, self.NUM_FLOORS - 1)
        y = self.floors_y[floor]
        roll = random.random()
        if roll < 0.45:
            room = random.choice(self.classrooms[floor])
            x = room.center[0] + random.uniform(-5.0, 5.0)
            z = room.center[2] + random.uniform(-1.7, 1.7)
            return floor, [x, y, z], room.name
        elif roll < 0.90:
            x = random.uniform(-14.0, 14.0)
            z = random.uniform(-1.5, 1.5)
            return floor, [x, y, z], f"P{floor+1}_Pasillo"
        exit_zone = random.choice(self.exits[floor])
        x = exit_zone.center[0] + random.uniform(-0.8, 0.8)
        z = exit_zone.center[2] + random.uniform(-0.8, 0.8)
        return floor, [x, y, z], exit_zone.name

    def get_nearest_exit(self, floor: int, pos: List[float]) -> RoomZone:
        return min(
            self.exits[floor],
            key=lambda e: (e.center[0] - pos[0]) ** 2 + (e.center[2] - pos[2]) ** 2,
        )

    def get_room_containing(self, floor: int, pos: List[float]) -> Optional[RoomZone]:
        for room in self.classrooms[floor]:
            if abs(pos[0] - room.center[0]) <= room.size[0] * 0.5 and abs(pos[2] - room.center[2]) <= room.size[1] * 0.5:
                return room
        return None
