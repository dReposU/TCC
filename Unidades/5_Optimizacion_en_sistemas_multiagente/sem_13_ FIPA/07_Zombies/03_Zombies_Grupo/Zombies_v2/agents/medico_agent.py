"""
Agente Médico en la universidad de 8 pisos (desplegado en pisos pares).
Equipado con un número limitado de dosis de antídoto (3 dosis por médico).
Intercepta a zombies recién infectados (is_converted == True), envía REQUEST ("aplicar_cura")
para revertirlos a PersonaAgent sano (zombie grande requiere 2 dosis, zombie normal 1 dosis),
y los escolta hacia la salida de emergencia más cercana.
"""
import math
import random
from typing import List, Optional, Tuple

from agents.acl import AID, ACLMessage, Performative, DFService
from agents.behaviours import BaseAgent, CyclicBehaviour, ParallelBehaviour


class MedicoReceiverBehaviour(CyclicBehaviour):
    def action(self, dt: float) -> None:
        medico: MedicoAgent = self.my_agent  # type: ignore
        msg = medico.receive()
        if msg is None:
            return

        if msg.performative == Performative.CONFIRM and msg.content == "cura_aceptada":
            humano_nombre = msg.data.get("humano")
            if humano_nombre:
                medico.target_humano_escort = humano_nombre
                medico.estado = "ESCOLTANDO"
                if medico.platform:
                    medico.platform.log(
                        f"{medico.local_name}: Escoltando a {humano_nombre} hacia la salida",
                        (140, 240, 255),
                    )


class MedicoActionBehaviour(CyclicBehaviour):
    def action(self, dt: float) -> None:
        medico: MedicoAgent = self.my_agent  # type: ignore
        if not medico.alive or medico.platform is None:
            return

        building = medico.platform.building
        from agents.persona_agent import PersonaAgent
        from agents.zombie_agent import ZombieAgent

        # -------------------------------------------------------------
        # ESTADO: ESCOLTANDO
        # -------------------------------------------------------------
        if medico.estado == "ESCOLTANDO":
            humano_escort = medico.platform.agents.get(medico.target_humano_escort or "")
            # Si el humano ya no existe o ya fue salvado, terminar escolta
            if humano_escort is None or not humano_escort.alive or getattr(humano_escort, "estado", "") != "SANO":
                medico.target_humano_escort = None
                if medico.dosis > 0:
                    medico.estado = "PATRULLANDO"
                else:
                    medico.estado = "EVACUANDO"
                return

            # Guiar hacia la salida más segura y cercana
            exits = building.exits[medico.floor]
            best_exit = building.get_nearest_exit(medico.floor, medico.position)
            tx, tz = best_exit.center[0], best_exit.center[2]

            dx = tx - medico.position[0]
            dz = tz - medico.position[2]
            dist_exit = max(1e-5, math.hypot(dx, dz))
            vx, vz = dx / dist_exit, dz / dist_exit

            speed = medico.run_speed
            medico.position[0] = max(-17.6, min(17.6, medico.position[0] + vx * speed * dt))
            medico.position[2] = max(-7.6, min(7.6, medico.position[2] + vz * speed * dt))
            desired_yaw = math.atan2(vx, vz)
            diff = (desired_yaw - medico.yaw + math.pi) % (2 * math.pi) - math.pi
            medico.yaw += diff * min(1.0, 12.0 * dt)
            medico.walk_phase += dt * speed * 3.4

            # Verificar si llegó a la salida junto al humano
            if dist_exit <= 1.4:
                d_humano = math.hypot(
                    humano_escort.position[0] - best_exit.center[0],
                    humano_escort.position[2] - best_exit.center[2],
                )
                if d_humano <= 1.6 and isinstance(humano_escort, PersonaAgent):
                    humano_escort.salvar(best_exit.name)

                medico.target_humano_escort = None
                if medico.dosis > 0:
                    medico.estado = "PATRULLANDO"
                    medico.pick_new_patrol_target()
                else:
                    medico.salvar(best_exit.name)
                return

            return

        # -------------------------------------------------------------
        # ESTADO: EVACUANDO (cuando se queda sin dosis)
        # -------------------------------------------------------------
        if medico.estado == "EVACUANDO" or medico.dosis <= 0:
            best_exit = building.get_nearest_exit(medico.floor, medico.position)
            dx = best_exit.center[0] - medico.position[0]
            dz = best_exit.center[2] - medico.position[2]
            dist = max(1e-5, math.hypot(dx, dz))
            if dist <= 1.25:
                medico.salvar(best_exit.name)
                return
            vx, vz = dx / dist, dz / dist
            speed = medico.run_speed
            medico.position[0] = max(-17.6, min(17.6, medico.position[0] + vx * speed * dt))
            medico.position[2] = max(-7.6, min(7.6, medico.position[2] + vz * speed * dt))
            desired_yaw = math.atan2(vx, vz)
            diff = (desired_yaw - medico.yaw + math.pi) % (2 * math.pi) - math.pi
            medico.yaw += diff * min(1.0, 12.0 * dt)
            medico.walk_phase += dt * speed * 3.4
            return

        # -------------------------------------------------------------
        # ESTADO: PATRULLANDO E INTERCEPTANDO ZOMBIES CONVERTIDOS
        # -------------------------------------------------------------
        converted_zombies = [
            a for a in medico.platform.agents.values()
            if isinstance(a, ZombieAgent) and a.alive and a.floor == medico.floor and a.is_converted
        ]

        # Filtrar zombies para los cuales el médico tiene dosis suficientes:
        # Zombie grande = 2 dosis, Zombie normal = 1 dosis
        curables = [
            z for z in converted_zombies
            if (2 if z.tipo_zombie == "GRANDE" else 1) <= medico.dosis
        ]

        # Zombies peligrosos que no puede curar (o zombies salvajes no convertidos)
        amenazas = [
            a for a in medico.platform.agents.values()
            if isinstance(a, ZombieAgent) and a.alive and a.floor == medico.floor and a not in curables
        ]

        # Si hay zombies curables, buscar el más cercano para interceptarlo
        target_zombie: Optional[ZombieAgent] = None
        min_target_dist = 999.0
        for cz in curables:
            d = math.hypot(cz.position[0] - medico.position[0], cz.position[2] - medico.position[2])
            if d < min_target_dist:
                min_target_dist = d
                target_zombie = cz

        # Si hay una amenaza inminente muy cerca (dist < 2.5), evadir primero
        nearest_threat: Optional[ZombieAgent] = None
        min_threat_dist = 999.0
        for am in amenazas:
            d = math.hypot(am.position[0] - medico.position[0], am.position[2] - medico.position[2])
            if d < min_threat_dist:
                min_threat_dist = d
                nearest_threat = am

        if target_zombie is not None:
            cost = 2 if target_zombie.tipo_zombie == "GRANDE" else 1

            # Si ya está dentro del rango de intercepción (<= 1.45m), aplicar cura
            if min_target_dist <= 1.45:
                # Enviar REQUEST "aplicar_cura" vía FIPA-ACL
                req = ACLMessage(
                    performative=Performative.REQUEST,
                    content="aplicar_cura",
                    data={
                        "medico": medico.local_name,
                        "dosis_usadas": cost,
                        "piso": medico.floor + 1,
                    },
                )
                req.add_receiver(target_zombie.aid)
                medico.send(req)

                medico.dosis -= cost
                medico.estado = "ESCOLTANDO"
                if medico.platform:
                    medico.platform.log(
                        f"{medico.local_name}: Aplicando cura a {target_zombie.local_name} (usó {cost} dosis, le restan {medico.dosis})",
                        (100, 245, 200),
                    )
                return

            # Moverse para interceptar al zombie curable
            if min_target_dist <= 3.2:
                tx, tz = target_zombie.position[0], target_zombie.position[2]
            else:
                p_room = building.get_room_containing(medico.floor, target_zombie.position)
                m_room = building.get_room_containing(medico.floor, medico.position)
                if p_room != m_room:
                    if m_room is not None:
                        tx, tz = m_room.door_pos[0], m_room.door_pos[2]
                    elif p_room is not None:
                        tx, tz = p_room.door_pos[0], p_room.door_pos[2]
                    else:
                        tx, tz = target_zombie.position[0], target_zombie.position[2]
                else:
                    tx, tz = target_zombie.position[0], target_zombie.position[2]

            dx = tx - medico.position[0]
            dz = tz - medico.position[2]
            dist = max(1e-5, math.hypot(dx, dz))
            vx, vz = dx / dist, dz / dist
            speed = medico.run_speed
        else:
            # No hay zombies curables visibles en este piso
            # Si hay amenazas cercanas no curables, alejarse
            if nearest_threat is not None and min_threat_dist < 5.0:
                away_x = medico.position[0] - nearest_threat.position[0]
                away_z = medico.position[2] - nearest_threat.position[2]
                alen = max(1e-5, math.hypot(away_x, away_z))
                vx, vz = away_x / alen, away_z / alen
                speed = medico.run_speed
            else:
                # Patrullar pasillos y aulas buscando infectados
                dx = medico.patrol_target[0] - medico.position[0]
                dz = medico.patrol_target[1] - medico.position[2]
                dist = math.hypot(dx, dz)
                if dist < 1.0:
                    medico.pick_new_patrol_target()
                    dx = medico.patrol_target[0] - medico.position[0]
                    dz = medico.patrol_target[1] - medico.position[2]
                    dist = max(1e-5, math.hypot(dx, dz))
                vx, vz = dx / dist, dz / dist
                speed = medico.walk_speed

        medico.position[0] = max(-17.5, min(17.5, medico.position[0] + vx * speed * dt))
        medico.position[2] = max(-7.5, min(7.5, medico.position[2] + vz * speed * dt))
        desired_yaw = math.atan2(vx, vz)
        diff = (desired_yaw - medico.yaw + math.pi) % (2 * math.pi) - math.pi
        medico.yaw += diff * min(1.0, 12.0 * dt)
        medico.walk_phase += dt * speed * 3.2


class MedicoAgent(BaseAgent):
    def __init__(
        self,
        local_name: str,
        floor: int,
        spawn_pos: List[float],
        spawn_zone: str,
        dosis: int = 3,
    ) -> None:
        super().__init__(local_name)
        self.floor = floor
        self.position = list(spawn_pos)
        self.spawn_zone = spawn_zone
        self.dosis = dosis
        self.dosis_iniciales = dosis
        self.estado: str = "PATRULLANDO"  # "PATRULLANDO", "ESCOLTANDO", "EVACUANDO", "SALVADO"
        self.target_humano_escort: Optional[str] = None

        self.scale: float = 0.94
        self.collision_radius: float = 0.38
        self.walk_speed: float = 2.8
        self.run_speed: float = 4.3
        self.yaw: float = random.uniform(-math.pi, math.pi)
        self.walk_phase: float = random.uniform(0.0, 6.28)
        self.patrol_target: Tuple[float, float] = (spawn_pos[0], spawn_pos[2])

        # Vestimenta médica blanca
        self.color: Tuple[int, int, int] = (250, 250, 254)
        self.limb_color: Tuple[int, int, int] = (238, 242, 250)
        self.is_medico: bool = True

    def setup(self) -> None:
        DFService.register(self)
        self.pick_new_patrol_target()
        parallel = ParallelBehaviour(self)
        parallel.add_sub_behaviour(MedicoReceiverBehaviour(self))
        parallel.add_sub_behaviour(MedicoActionBehaviour(self))
        self.add_behaviour(parallel)

    def pick_new_patrol_target(self) -> None:
        if self.platform is None:
            return
        building = self.platform.building
        roll = random.random()
        if roll < 0.60:
            self.patrol_target = (random.uniform(-14.0, 14.0), random.uniform(-1.2, 1.2))
        else:
            room = random.choice(building.classrooms[self.floor])
            self.patrol_target = (
                room.center[0] + random.uniform(-4.0, 4.0),
                room.center[2] + random.uniform(-1.4, 1.4),
            )

    def salvar(self, exit_name: str) -> None:
        if self.estado == "SALVADO":
            return
        self.estado = "SALVADO"
        if self.platform is not None:
            self.platform.log(
                f"{self.local_name}: MÉDICO a salvo por {exit_name} (dosis restantes: {self.dosis})",
                (120, 255, 180),
            )
            self.platform.spawn_effect(self.position, (120, 255, 180), "MÉDICO A SALVO!")
            self.platform.trigger_sound("escape_safe")
        self.do_delete()
