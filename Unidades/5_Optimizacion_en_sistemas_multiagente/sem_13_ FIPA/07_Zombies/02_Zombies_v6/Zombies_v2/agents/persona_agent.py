"""
Agente Persona (Estudiante / Docente) en la universidad de 8 pisos.
Busca las 3 salidas de emergencia de su piso, evade zombies cercanos
y se salva al salir del edificio o se infecta si es mordido.
"""
import math
import random
from typing import List, Optional, Tuple
from agents.acl import AID, ACLMessage, Performative, DFService
from agents.behaviours import BaseAgent, CyclicBehaviour, ParallelBehaviour, TickerBehaviour


class PersonaReportTicker(TickerBehaviour):
    def on_tick(self) -> None:
        persona: PersonaAgent = self.my_agent  # type: ignore
        if persona.estado != "SANO":
            return
        msg = ACLMessage(performative=Performative.INFORM, content="evacuando")
        msg.add_receiver(AID("Edificio", is_local_name=True))
        persona.send(msg)


class PersonaReceiverBehaviour(CyclicBehaviour):
    def action(self, dt: float) -> None:
        persona: PersonaAgent = self.my_agent  # type: ignore
        msg = persona.receive()
        if msg is None:
            return
        if msg.performative == Performative.ALERT and msg.content == "peligro_zombie":
            persona.panico_timer = 2.0


class PersonaEvacuateBehaviour(CyclicBehaviour):
    def action(self, dt: float) -> None:
        persona: PersonaAgent = self.my_agent  # type: ignore
        if persona.estado != "SANO" or persona.platform is None:
            return

        building = persona.platform.building
        from agents.zombie_agent import ZombieAgent

        zombies_piso = [
            a for a in persona.platform.agents.values()
            if isinstance(a, ZombieAgent) and a.alive and a.floor == persona.floor
        ]

        nearest_zombie: Optional[ZombieAgent] = None
        min_z_dist = 999.0
        for z in zombies_piso:
            d = math.hypot(z.position[0] - persona.position[0], z.position[2] - persona.position[2])
            if d < min_z_dist:
                min_z_dist = d
                nearest_zombie = z

        current_room = building.get_room_containing(persona.floor, persona.position)
        if current_room is not None:
            target_x, target_z = current_room.door_pos[0], current_room.door_pos[2]
        else:
            exits = building.exits[persona.floor]
            best_exit = exits[0]
            best_score = 1e9
            for ex in exits:
                dist_p = math.hypot(ex.center[0] - persona.position[0], ex.center[2] - persona.position[2])
                penalty = 0.0
                for z in zombies_piso:
                    dz_exit = math.hypot(z.position[0] - ex.center[0], z.position[2] - ex.center[2])
                    if dz_exit < 4.5:
                        penalty += (4.5 - dz_exit) * 8.0
                score = dist_p + penalty
                if score < best_score:
                    best_score = score
                    best_exit = ex
            target_x, target_z = best_exit.center[0], best_exit.center[2]

        dx = target_x - persona.position[0]
        dz = target_z - persona.position[2]
        dist_target = max(1e-5, math.hypot(dx, dz))
        vx, vz = dx / dist_target, dz / dist_target

        is_fleeing = False
        if nearest_zombie is not None and min_z_dist < 6.0:
            is_fleeing = True
            away_x = persona.position[0] - nearest_zombie.position[0]
            away_z = persona.position[2] - nearest_zombie.position[2]
            away_len = max(1e-5, math.hypot(away_x, away_z))
            weight = (6.0 - min_z_dist) / 6.0 * 1.35
            vx += (away_x / away_len) * weight
            vz += (away_z / away_len) * weight
            v_norm = max(1e-5, math.hypot(vx, vz))
            vx, vz = vx / v_norm, vz / v_norm

        speed = persona.run_speed if (is_fleeing or persona.panico_timer > 0.0) else persona.walk_speed
        if persona.panico_timer > 0.0:
            persona.panico_timer -= dt

        persona.position[0] = max(-17.6, min(17.6, persona.position[0] + vx * speed * dt))
        persona.position[2] = max(-7.6, min(7.6, persona.position[2] + vz * speed * dt))
        persona.yaw = math.atan2(vx, vz)
        persona.walk_phase += dt * speed * 3.4
        persona.is_running = is_fleeing

        for ex in building.exits[persona.floor]:
            d_exit = math.hypot(ex.center[0] - persona.position[0], ex.center[2] - persona.position[2])
            if d_exit <= 1.25:
                persona.salvar(ex.name)
                return


class PersonaAgent(BaseAgent):
    def __init__(self, local_name: str, floor: int, spawn_pos: List[float], spawn_zone: str) -> None:
        super().__init__(local_name)
        self.floor = floor
        self.position = list(spawn_pos)
        self.spawn_zone = spawn_zone
        self.estado: str = "SANO"
        self.walk_speed: float = random.uniform(2.5, 3.2)
        self.run_speed: float = random.uniform(3.9, 4.6)
        self.yaw: float = random.uniform(-math.pi, math.pi)
        self.walk_phase: float = random.uniform(0.0, 6.28)
        self.is_running: bool = False
        self.panico_timer: float = 0.0
        self.color: Tuple[int, int, int] = random.choice([
            (70, 175, 255),
            (95, 215, 245),
            (245, 210, 85),
            (130, 195, 255),
            (255, 165, 90),
        ])

    def setup(self) -> None:
        DFService.register(self)
        parallel = ParallelBehaviour(self)
        delay = random.uniform(300.0, 4200.0)
        parallel.add_sub_behaviour(PersonaReportTicker(self, 4500, initial_delay_ms=delay))
        parallel.add_sub_behaviour(PersonaReceiverBehaviour(self))
        parallel.add_sub_behaviour(PersonaEvacuateBehaviour(self))
        self.add_behaviour(parallel)

    def salvar(self, exit_name: str) -> None:
        if self.estado != "SANO":
            return
        self.estado = "SALVADO"
        if self.platform is not None:
            self.platform.total_salvados += 1
            msg = ACLMessage(
                performative=Performative.INFORM,
                content="salvado",
                data={"salida": exit_name, "piso": self.floor + 1},
            )
            msg.add_receiver(AID("Edificio", is_local_name=True))
            self.send(msg)
            self.platform.spawn_effect(self.position, (80, 255, 145), "SALVADO!")
            self.platform.trigger_sound("escape_safe")
        self.do_delete()

    def infectar(self, attacker_name: str) -> None:
        if self.estado != "SANO":
            return
        self.estado = "INFECTADO"
        if self.platform is not None:
            self.platform.total_infectados += 1
            self.platform.spawn_effect(self.position, (255, 70, 70), "INFECTADO!")
            self.platform.trigger_sound("alert_bite")

            from agents.zombie_agent import ZombieAgent
            z_id = self.platform.next_zombie_id()
            nuevo_zombie = ZombieAgent(
                local_name=f"Zombie_Inf_{z_id}",
                floor=self.floor,
                spawn_pos=list(self.position),
                spawn_zone=f"P{self.floor+1}_Infeccion",
                is_converted=True,
            )
            self.platform.register_agent(nuevo_zombie)
        self.do_delete()
