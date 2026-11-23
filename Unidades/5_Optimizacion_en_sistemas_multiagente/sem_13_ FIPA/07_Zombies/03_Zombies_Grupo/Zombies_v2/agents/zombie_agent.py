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
            and getattr(a, "inmunidad_timer", 0.0) <= 0.0
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
            # Si el humano está a distancia cercana (<= 3.2m), perseguirlo directamente sin desvíos de puertas
            if min_dist <= 3.2:
                tx, tz = target_person.position[0], target_person.position[2]
            else:
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

            if min_dist <= zombie.bite_dist:
                zombie.bite_anim_timer = 0.65
                msg = ACLMessage(
                    performative=Performative.ALERT,
                    content="mordida",
                    data={
                        "victima": target_person.local_name,
                        "piso": zombie.floor + 1,
                        "tipo_humano": getattr(target_person, "tipo_humano", "HUMANO"),
                        "atacante_tipo": zombie.tipo_zombie,
                    },
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
        desired_yaw = math.atan2(vx, vz)
        diff = (desired_yaw - zombie.yaw + math.pi) % (2 * math.pi) - math.pi
        zombie.yaw += diff * min(1.0, 12.0 * dt)
        zombie.walk_phase += dt * speed * 3.1


class ZombieAlertTicker(TickerBehaviour):
    def on_tick(self) -> None:
        zombie: ZombieAgent = self.my_agent  # type: ignore
        if not zombie.alive or not zombie.chasing or zombie.platform is None:
            return
        from agents.persona_agent import PersonaAgent
        alert_radius = 11.5 if zombie.tipo_zombie == "GRANDE" else 8.5
        for a in zombie.platform.agents.values():
            if isinstance(a, PersonaAgent) and a.alive and a.floor == zombie.floor:
                d = math.hypot(a.position[0] - zombie.position[0], a.position[2] - zombie.position[2])
                if d < alert_radius:
                    msg = ACLMessage(performative=Performative.ALERT, content="peligro_zombie")
                    msg.add_receiver(a.aid)
                    zombie.send(msg)


class ZombieReceiverBehaviour(CyclicBehaviour):
    def action(self, dt: float) -> None:
        zombie: ZombieAgent = self.my_agent  # type: ignore
        msg = zombie.receive()
        if msg is None:
            return
        if msg.performative == Performative.REQUEST and msg.content == "aplicar_cura":
            if zombie.is_converted and zombie.alive:
                zombie.revertir_a_humano(msg)


class ZombieAgent(BaseAgent):
    def __init__(
        self,
        local_name: str,
        floor: int,
        spawn_pos: List[float],
        spawn_zone: str,
        is_converted: bool = False,
        tipo_zombie: str = "NORMAL",
        original_tipo_humano: str = "DEBIL",
        original_persona_name: str = "",
    ) -> None:
        super().__init__(local_name)
        self.floor = floor
        self.position = list(spawn_pos)
        self.spawn_zone = spawn_zone
        self.is_converted = is_converted
        self.tipo_zombie = tipo_zombie  # "NORMAL" o "GRANDE"
        self.original_tipo_humano = original_tipo_humano
        self.original_persona_name = original_persona_name

        if self.tipo_zombie == "GRANDE":
            self.scale: float = 1.45
            self.collision_radius: float = 0.55
            self.patrol_speed: float = random.uniform(1.2, 1.7)
            self.chase_speed: float = random.uniform(3.4, 4.05)
            self.vision_radius: float = 16.5
            self.bite_dist: float = 1.45
            self.color: Tuple[int, int, int] = (195, 30, 45)
            self.limb_color: Tuple[int, int, int] = (160, 20, 35)
        else:
            self.scale: float = 0.92
            self.collision_radius: float = 0.40
            self.patrol_speed: float = random.uniform(1.4, 2.0)
            self.chase_speed: float = random.uniform(3.2, 3.85)
            self.vision_radius: float = 14.5
            self.bite_dist: float = 1.15
            self.color: Tuple[int, int, int] = (225, 75, 85) if is_converted else (75, 205, 95)
            self.limb_color: Tuple[int, int, int] = (195, 60, 70) if is_converted else (95, 185, 95)

        self.chasing: bool = False
        self.bite_anim_timer: float = 0.0
        self.yaw: float = random.uniform(-math.pi, math.pi)
        self.walk_phase: float = random.uniform(0.0, 6.28)
        self.patrol_target: Tuple[float, float] = (spawn_pos[0], spawn_pos[2])

    def setup(self) -> None:
        DFService.register(self)
        self.pick_new_patrol_target()
        parallel = ParallelBehaviour(self)
        parallel.add_sub_behaviour(ZombiePatrolAndHuntBehaviour(self))
        parallel.add_sub_behaviour(ZombieAlertTicker(self, 3500, initial_delay_ms=random.uniform(200, 3000)))
        parallel.add_sub_behaviour(ZombieReceiverBehaviour(self))
        self.add_behaviour(parallel)

    def revertir_a_humano(self, msg: ACLMessage) -> None:
        if not self.alive or not self.is_converted or self.platform is None:
            return

        # Revertir estadísticas en la plataforma
        self.platform.total_infectados = max(0, self.platform.total_infectados - 1)
        if self.tipo_zombie == "GRANDE":
            self.platform.total_transformados_grandes = max(0, self.platform.total_transformados_grandes - 1)
            self.platform.total_curados_grandes += 1
            tipo_restaurado = "FUERTE"
        else:
            self.platform.total_transformados_normales = max(0, self.platform.total_transformados_normales - 1)
            self.platform.total_curados_normales += 1
            tipo_restaurado = getattr(self, "original_tipo_humano", "DEBIL")

        self.platform.total_curados += 1

        medico_name = msg.data.get("medico", "Médico")
        dosis_usadas = msg.data.get("dosis_usadas", 1)
        c_id = self.platform.next_cured_id()
        nombre_humano = f"Humano_Curado_{c_id}"

        # Efecto visual y sonoro de cura
        self.platform.spawn_effect(self.position, (70, 245, 220), "¡CURADO!")
        self.platform.trigger_sound("escape_safe")

        # Notificar al Edificio sobre la cura exitosa
        info_msg = ACLMessage(
            performative=Performative.INFORM,
            content="cura_exitosa",
            data={
                "medico": medico_name,
                "zombie_curado": self.local_name,
                "humano_restaurado": nombre_humano,
                "tipo_humano": tipo_restaurado,
                "tipo_zombie": self.tipo_zombie,
                "dosis_usadas": dosis_usadas,
                "piso": self.floor + 1,
            },
        )
        info_msg.add_receiver(AID("Edificio", is_local_name=True))
        self.send(info_msg)

        # Confirmar al médico para que inicie la escolta
        reply = msg.create_reply(Performative.CONFIRM)
        reply.content = "cura_aceptada"
        reply.data = {"humano": nombre_humano, "posicion": list(self.position)}
        self.send(reply)

        # Reaparecer como PersonaAgent sano
        from agents.persona_agent import PersonaAgent
        nuevo_humano = PersonaAgent(
            local_name=nombre_humano,
            floor=self.floor,
            spawn_pos=list(self.position),
            spawn_zone=f"P{self.floor+1}_Curacion",
            tipo_humano=tipo_restaurado,
            medico_escort=medico_name,
        )
        nuevo_humano.yaw = self.yaw
        self.platform.register_agent(nuevo_humano)

        self.do_delete()

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
