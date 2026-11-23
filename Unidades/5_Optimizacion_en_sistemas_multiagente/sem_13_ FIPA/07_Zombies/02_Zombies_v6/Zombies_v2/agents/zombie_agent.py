"""
Agente Zombie en la universidad de 8 pisos.
Patrulla salones, pasillos y (con poca probabilidad) zonas cercanas a salidas de emergencia.
Persigue personas en su piso y las infecta al morderlas.

Caza coordinada (FIPA-ACL):
- Cuando un zombie entra en estado de persecución (chasing: False -> True) envía un
  INFORM "presa_detectada" a todos los zombies en un radio de 12.0 m (distancia 3D,
  por lo que incluye zombies de pisos adyacentes).
- El mensaje incluye la ubicación de la presa y una asignación de salida por receptor,
  de modo que los zombies se reparten las salidas del piso (primero la salida más
  probable de la presa) en lugar de amontonarse en un solo punto.
- Los receptores abandonan la patrulla aleatoria y convergen hacia la salida asignada
  para emboscarla. Si están en un piso adyacente, primero usan la escalera de
  emergencia más cercana (las salidas) para cambiar al piso de la presa.
"""
import math
import random
from typing import Dict, List, Optional, Tuple
from agents.acl import AID, ACLMessage, Performative, DFService
from agents.behaviours import BaseAgent, ParallelBehaviour, TickerBehaviour, CyclicBehaviour


# Parámetros de la caza coordinada
RADIO_COMUNICACION = 12.0      # m, radio 3D del INFORM "presa_detectada"
COOLDOWN_AVISO = 4.0           # s mínimos entre dos avisos del mismo zombie
DURACION_EMBOSCADA = 12.0      # s que un zombie mantiene la emboscada antes de volver a patrullar
OFFSET_EMBOSCADA = 1.6         # m que el zombie se ubica "hacia adentro" de la salida
RADIO_LLEGADA = 0.6            # m para considerar alcanzado un punto de emboscada
RADIO_ESCALERA = 1.0           # m para usar una escalera/salida y cambiar de piso
RADIO_ATAQUE_EMBOSCADA = 4.0   # m: un zombie emboscando solo se lanza si la presa se acerca a esta distancia

# Navegación / colisiones
RADIO_PUERTA = 0.8             # m: al estar a esta distancia de una puerta, la cruza
RADIO_SEPARACION = 0.9         # m: distancia mínima deseada entre zombies


def _dist_xz(a: List[float], b) -> float:
    return math.hypot(a[0] - b[0], a[2] - b[2])


def _punto_emboscada(exit_center: Tuple[float, float, float]) -> Tuple[float, float]:
    """Punto ligeramente hacia el interior del edificio respecto a la salida,
    para interceptar a quien llegue por el pasillo."""
    ex, ez = exit_center[0], exit_center[2]
    n = max(1e-5, math.hypot(ex, ez))
    return ex - ex / n * OFFSET_EMBOSCADA, ez - ez / n * OFFSET_EMBOSCADA


class ZombiePatrolAndHuntBehaviour(CyclicBehaviour):
    def action(self, dt: float) -> None:
        zombie: ZombieAgent = self.my_agent  # type: ignore
        if not zombie.alive or zombie.platform is None:
            return

        if zombie.bite_anim_timer > 0.0:
            zombie.bite_anim_timer = max(0.0, zombie.bite_anim_timer - dt)
        if zombie.aviso_cooldown > 0.0:
            zombie.aviso_cooldown = max(0.0, zombie.aviso_cooldown - dt)

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

        # Un zombie en emboscada mantiene su posición en la salida y solo se lanza
        # sobre una presa cuando ésta entra en su radio de ataque.
        rango_persecucion = RADIO_ATAQUE_EMBOSCADA if zombie.emboscada is not None else zombie.vision_radius

        if target_person is not None and min_dist <= rango_persecucion:
            # --- Transición a persecución: avisar a la manada ---
            if not zombie.chasing:
                zombie.chasing = True
                zombie.desde_emboscada = zombie.emboscada is not None
                zombie.cancelar_emboscada()
                zombie.notificar_presa(target_person)

            tx, tz = zombie._navegar(target_person.position[0], target_person.position[2])

            dx = tx - zombie.position[0]
            dz = tz - zombie.position[2]
            dist = max(1e-5, math.hypot(dx, dz))
            vx, vz = dx / dist, dz / dist
            speed = zombie.chase_speed

            if min_dist <= 1.15:
                zombie.bite_anim_timer = 0.65
                if zombie.desde_emboscada:
                    zombie.platform.infectados_por_horda += 1
                    zombie.platform.spawn_effect(zombie.position, (255, 150, 40), "EMBOSCADA!")
                zombie.desde_emboscada = False
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
            zombie.desde_emboscada = False

            if zombie.emboscada is not None:
                # --- Modo emboscada: converger hacia la salida asignada ---
                mov = zombie.paso_emboscada(dt)
                if mov is None:
                    return  # esperando en posición o acaba de cambiar de piso
                vx, vz, speed = mov
            else:
                # --- Patrulla aleatoria original ---
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

        # Separación entre zombies: evita que se apilen en el mismo punto
        # (p. ej. el zombie recién convertido aparece encima del que mordió).
        sx, sz = zombie.separacion()
        vx += sx
        vz += sz
        v_norm = math.hypot(vx, vz)
        if v_norm > 1.0:
            vx, vz = vx / v_norm, vz / v_norm

        zombie.position[0] = max(-17.5, min(17.5, zombie.position[0] + vx * speed * dt))
        zombie.position[2] = max(-7.5, min(7.5, zombie.position[2] + vz * speed * dt))
        if abs(vx) + abs(vz) > 1e-4:
            zombie.yaw = math.atan2(vx, vz)
        zombie.walk_phase += dt * speed * 3.1


class ZombieReceiverBehaviour(CyclicBehaviour):
    """Procesa los INFORM "presa_detectada" enviados por otros zombies."""

    def action(self, dt: float) -> None:
        zombie: ZombieAgent = self.my_agent  # type: ignore
        if not zombie.alive or zombie.platform is None:
            return
        msg = zombie.receive()
        while msg is not None:
            if msg.performative == Performative.INFORM and msg.content == "presa_detectada":
                zombie.recibir_presa_detectada(msg)
            msg = zombie.receive()


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

        # Estado de caza coordinada
        self.aviso_cooldown: float = 0.0
        self.desde_emboscada: bool = False   # True si la persecución actual empezó desde una emboscada
        # emboscada = {"piso": int, "salida": str, "punto": (x, z), "presa": str,
        #              "timer": float, "emisor": str}
        self.emboscada: Optional[Dict] = None

    def setup(self) -> None:
        DFService.register(self)
        self.pick_new_patrol_target()
        parallel = ParallelBehaviour(self)
        parallel.add_sub_behaviour(ZombiePatrolAndHuntBehaviour(self))
        parallel.add_sub_behaviour(ZombieReceiverBehaviour(self))
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

    # ------------------------------------------------------------------
    # Emisor: INFORM "presa_detectada"
    # ------------------------------------------------------------------
    def _distancia_3d(self, otro: "ZombieAgent") -> float:
        dx = otro.position[0] - self.position[0]
        dz = otro.position[2] - self.position[2]
        dy = (otro.floor - self.floor) * self.platform.building.FLOOR_HEIGHT  # type: ignore
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def notificar_presa(self, presa) -> None:
        """Envía INFORM "presa_detectada" a los zombies dentro de RADIO_COMUNICACION
        (mismo piso o pisos adyacentes) y les asigna salidas a emboscar."""
        if self.platform is None or self.aviso_cooldown > 0.0:
            return
        if not self.platform.modo_horda:
            return  # modo horda desactivado (tecla H): comportamiento original sin coordinación
        building = self.platform.building

        receptores: List[ZombieAgent] = [
            a for a in self.platform.agents.values()
            if isinstance(a, ZombieAgent) and a is not self and a.alive
            and abs(a.floor - self.floor) <= 1
            and self._distancia_3d(a) <= RADIO_COMUNICACION
        ]
        if not receptores:
            return

        # Salidas del piso de la presa ordenadas por cercanía a la presa:
        # la primera es la ruta de escape más probable.
        salidas = sorted(building.exits[self.floor], key=lambda e: _dist_xz(presa.position, e.center))

        # Reparto coordinado: los zombies más cercanos a cada salida la cubren,
        # empezando por la salida más probable; luego se repite en round-robin.
        asignaciones: Dict[str, str] = {}
        pendientes = list(receptores)
        idx = 0
        while pendientes:
            salida = salidas[idx % len(salidas)]
            elegido = min(
                pendientes,
                key=lambda z: _dist_xz(z.position, salida.center) + abs(z.floor - self.floor) * 6.0,
            )
            asignaciones[elegido.local_name] = salida.name
            pendientes.remove(elegido)
            idx += 1

        msg = ACLMessage(
            performative=Performative.INFORM,
            content="presa_detectada",
            data={
                "presa": presa.local_name,
                "piso": self.floor,
                "x": presa.position[0],
                "z": presa.position[2],
                "asignaciones": asignaciones,
            },
        )
        for z in receptores:
            msg.add_receiver(z.aid)
        self.send(msg)
        self.aviso_cooldown = COOLDOWN_AVISO
        self.platform.total_avisos_horda += 1

        self.platform.log(
            f"{self.local_name}: INFORM presa_detectada ({presa.local_name}, Piso {self.floor+1}) "
            f"-> {len(receptores)} zombies",
            (255, 175, 70),
        )

    # ------------------------------------------------------------------
    # Receptor: abandonar patrulla y emboscar la salida asignada
    # ------------------------------------------------------------------
    def recibir_presa_detectada(self, msg: ACLMessage) -> None:
        if self.platform is None or not self.platform.modo_horda:
            return
        if self.chasing:
            # Si ya persigue a alguien muy cerca, sigue en lo suyo; si no, se une a la emboscada.
            presa_propia_cerca = any(
                getattr(a, "estado", "") == "SANO" and a.floor == self.floor
                and _dist_xz(self.position, a.position) <= RADIO_ATAQUE_EMBOSCADA
                for a in self.platform.agents.values() if a is not self and not isinstance(a, ZombieAgent)
            )
            if presa_propia_cerca:
                return
            self.chasing = False
        data = msg.data
        piso = int(data.get("piso", self.floor))
        if abs(piso - self.floor) > 1:
            return
        building = self.platform.building
        nombre_salida = data.get("asignaciones", {}).get(self.local_name)
        salidas = building.exits[piso]
        salida = next((e for e in salidas if e.name == nombre_salida), None)
        if salida is None:
            presa_pos = [data.get("x", 0.0), 0.0, data.get("z", 0.0)]
            salida = min(salidas, key=lambda e: _dist_xz(presa_pos, e.center))

        self.emboscada = {
            "piso": piso,
            "salida": salida.name,
            "punto": _punto_emboscada(salida.center),
            "presa": data.get("presa", ""),
            "timer": DURACION_EMBOSCADA,
            "emisor": msg.sender.local_name if msg.sender else "?",
        }

    def cancelar_emboscada(self) -> None:
        self.emboscada = None

    def paso_emboscada(self, dt: float) -> Optional[Tuple[float, float, float]]:
        """Devuelve (vx, vz, speed) hacia el objetivo de emboscada, o None si no hay que moverse."""
        assert self.platform is not None and self.emboscada is not None
        building = self.platform.building
        emb = self.emboscada

        emb["timer"] -= dt
        presa = self.platform.agents.get(emb["presa"])
        presa_activa = presa is not None and presa.alive and getattr(presa, "estado", "") == "SANO"
        if emb["timer"] <= 0.0 or not presa_activa or not self.platform.modo_horda:
            self.cancelar_emboscada()
            self.pick_new_patrol_target()
            return None

        speed = self.chase_speed * 0.9

        # 1) Si la presa está en un piso adyacente, ir a la escalera (salida) más cercana y cambiar de piso.
        if emb["piso"] != self.floor:
            escalera = building.get_nearest_exit(self.floor, self.position)
            if _dist_xz(self.position, escalera.center) <= RADIO_ESCALERA:
                origen = self.floor
                self.floor = emb["piso"]
                self.position[1] = building.floors_y[self.floor]
                self.platform.spawn_effect(
                    self.position, (255, 175, 70),
                    "SUBE" if self.floor > origen else "BAJA",
                )
                return None
            tx, tz = self._navegar(escalera.center[0], escalera.center[2])
        else:
            # 2) En el piso correcto: dirigirse al punto de emboscada y esperar ahí.
            px, pz = emb["punto"]
            if math.hypot(px - self.position[0], pz - self.position[2]) <= RADIO_LLEGADA:
                # En posición: mirar hacia el pasillo y esperar a la presa
                # (velocidad 0, solo actúa la separación con otros zombies).
                self.yaw = math.atan2(-px, -pz)
                return 0.0, 0.0, self.patrol_speed
            tx, tz = self._navegar(px, pz)

        dx = tx - self.position[0]
        dz = tz - self.position[2]
        dist = max(1e-5, math.hypot(dx, dz))
        return dx / dist, dz / dist, speed

    def _navegar(self, tx: float, tz: float) -> Tuple[float, float]:
        """Devuelve el siguiente punto de paso hacia (tx, tz) respetando puertas de aulas.

        FIX del atasco en puertas: la puerta (door_pos) está en el borde del aula pero
        FUERA de su área, así que antes un zombie en el pasillo que perseguía a alguien
        dentro de un aula llegaba a la puerta, seguía "fuera", volvía a apuntar a la
        misma puerta y se quedaba congelado ahí. Ahora, al llegar a la puerta,
        la atraviesa y sigue directo al objetivo.
        """
        building = self.platform.building  # type: ignore
        z_room = building.get_room_containing(self.floor, self.position)
        t_room = building.get_room_containing(self.floor, [tx, 0.0, tz])
        if z_room == t_room:
            return tx, tz
        if z_room is not None:
            puerta = z_room.door_pos       # salir primero del aula actual
        else:
            puerta = t_room.door_pos       # entrar al aula del objetivo (t_room no es None aquí)
        if _dist_xz(self.position, puerta) <= RADIO_PUERTA:
            # Ya está en la puerta: cruzarla en dirección al objetivo.
            return tx, tz
        return puerta[0], puerta[2]

    def separacion(self) -> Tuple[float, float]:
        """Fuerza de repulsión respecto a zombies muy cercanos del mismo piso."""
        if self.platform is None:
            return 0.0, 0.0
        fx = fz = 0.0
        for a in self.platform.agents.values():
            if a is self or not isinstance(a, ZombieAgent) or not a.alive or a.floor != self.floor:
                continue
            dx = self.position[0] - a.position[0]
            dz = self.position[2] - a.position[2]
            d = math.hypot(dx, dz)
            if d < RADIO_SEPARACION:
                if d < 1e-4:  # exactamente encima: empujar en una dirección aleatoria
                    ang = random.uniform(-math.pi, math.pi)
                    dx, dz, d = math.cos(ang), math.sin(ang), 1.0
                peso = (RADIO_SEPARACION - min(d, RADIO_SEPARACION)) / RADIO_SEPARACION
                fx += dx / d * peso * 1.5
                fz += dz / d * peso * 1.5
        return fx, fz
