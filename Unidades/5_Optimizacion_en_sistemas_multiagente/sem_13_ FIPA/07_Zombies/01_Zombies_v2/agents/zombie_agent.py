"""
Agente Zombie en la universidad de 8 pisos.
Patrulla salones, pasillos y (con poca probabilidad) zonas cercanas a salidas de emergencia.
Persigue personas en su piso y las infecta al morderlas.
"""
import math
import random
from typing import List, Optional, Tuple
from agents.acl import AID, ACLMessage, Performative, DFService
from agents.behaviours import BaseAgent, ParallelBehaviour, TickerBehaviour, CyclicBehaviour


class ZombiePatrolAndHuntBehaviour(CyclicBehaviour):
    def action(self, dt: float) -> None:
        zombie: ZombieAgent = self.my_agent  # type: ignore
        if not zombie.alive or zombie.platform is None:
            return

        if zombie.bite_anim_timer > 0.0:
            zombie.bite_anim_timer = max(0.0, zombie.bite_anim_timer - dt)

        building = zombie.platform.building
        from agents.persona_agent import PersonaAgent

        personas_piso = [
            a for a in zombie.platform.agents.values()
            if isinstance(a, PersonaAgent) and a.alive and a.estado == "SANO" and a.floor == zombie.floor
        ]

        target_person: Optional[PersonaAgent] = None
        min_dist = 999.0
        for p in personas_piso:
            d = math.hypot(p.position[0] - zombie.position[0], p.position[2] - zombie.position[2])
            if d < min_dist:
                min_dist = d
                target_person = p

        if target_person is not None and min_dist <= zombie.vision_radius:
            zombie.chasing = True
            p_room = building.get_room_containing(zombie.floor, target_person.position)
            z_room = building.get_room_containing(zombie.floor, zombie.position)
            if p_room != z_room:
                if z_room is not None:
                    tx, tz = z_room.door_pos[0], z_room.door_pos[2]
                elif p_room is not None:
                    tx, tz = p_room.door_pos[0], p_room.door_pos[2]
                else:
                    tx, tz = target_person.position[0], target_person.position[2]
            else:
                tx, tz = target_person.position[0], target_person.position[2]

            dx = tx - zombie.position[0]
            dz = tz - zombie.position[2]
            dist = max(1e-5, math.hypot(dx, dz))
            vx, vz = dx / dist, dz / dist
            speed = zombie.chase_speed

            if min_dist <= 1.15:
                zombie.bite_anim_timer = 0.65
                msg = ACLMessage(
                    performative=Performative.ALERT,
                    content="mordida",
                    data={"victima": target_person.local_name, "piso": zombie.floor + 1},
                )
                msg.add_receiver(AID("Edificio", is_local_name=True))
                zombie.send(msg)
                target_person.infectar(zombie.local_name)
                return
        else:
            zombie.chasing = False
            dx = zombie.patrol_target[0] - zombie.position[0]
            dz = zombie.patrol_target[1] - zombie.position[2]
            dist = math.hypot(dx, dz)
            if dist < 1.0:
                zombie.pick_new_patrol_target()
                dx = zombie.patrol_target[0] - zombie.position[0]
                dz = zombie.patrol_target[1] - zombie.position[2]
                dist = max(1e-5, math.hypot(dx, dz))
            vx, vz = dx / dist, dz / dist
            speed = zombie.patrol_speed

        zombie.position[0] = max(-17.5, min(17.5, zombie.position[0] + vx * speed * dt))
        zombie.position[2] = max(-7.5, min(7.5, zombie.position[2] + vz * speed * dt))
        zombie.yaw = math.atan2(vx, vz)
        zombie.walk_phase += dt * speed * 3.1


class ZombieAlertTicker(TickerBehaviour):
    def on_tick(self) -> None:
        zombie: ZombieAgent = self.my_agent  # type: ignore
        if not zombie.alive or not zombie.chasing or zombie.platform is None:
            return
        from agents.persona_agent import PersonaAgent
        for a in zombie.platform.agents.values():
            if isinstance(a, PersonaAgent) and a.alive and a.floor == zombie.floor:
                d = math.hypot(a.position[0] - zombie.position[0], a.position[2] - zombie.position[2])
                if d < 8.5:
                    msg = ACLMessage(performative=Performative.ALERT, content="peligro_zombie")
                    msg.add_receiver(a.aid)
                    zombie.send(msg)


class ZombieAgent(BaseAgent):
    def __init__(
        self,
        local_name: str,
        floor: int,
        spawn_pos: List[float],
        spawn_zone: str,
        is_converted: bool = False,
    ) -> None:
        super().__init__(local_name)
        self.floor = floor
        self.position = list(spawn_pos)
        self.spawn_zone = spawn_zone
        self.is_converted = is_converted
        self.patrol_speed: float = random.uniform(1.4, 2.0)
        self.chase_speed: float = random.uniform(3.2, 3.85)
        self.vision_radius: float = 14.5
        self.chasing: bool = False
        self.bite_anim_timer: float = 0.0
        self.yaw: float = random.uniform(-math.pi, math.pi)
        self.walk_phase: float = random.uniform(0.0, 6.28)
        self.patrol_target: Tuple[float, float] = (spawn_pos[0], spawn_pos[2])
        self.color: Tuple[int, int, int] = (225, 65, 85) if is_converted else (75, 205, 95)

    def setup(self) -> None:
        DFService.register(self)
        self.pick_new_patrol_target()
        parallel = ParallelBehaviour(self)
        parallel.add_sub_behaviour(ZombiePatrolAndHuntBehaviour(self))
        parallel.add_sub_behaviour(ZombieAlertTicker(self, 3500, initial_delay_ms=random.uniform(200, 3000)))
        self.add_behaviour(parallel)

    def pick_new_patrol_target(self) -> None:
        if self.platform is None:
            return
        building = self.platform.building
        roll = random.random()
        if roll < 0.45:
            room = random.choice(building.classrooms[self.floor])
            self.patrol_target = (
                room.center[0] + random.uniform(-4.5, 4.5),
                room.center[2] + random.uniform(-1.5, 1.5),
            )
        elif roll < 0.90:
            self.patrol_target = (random.uniform(-15.0, 15.0), random.uniform(-1.4, 1.4))
        else:
            ex = random.choice(building.exits[self.floor])
            self.patrol_target = (ex.center[0], ex.center[2])
