"""
Adaptación de AvionAgent.java con cinemática de vuelo 3D, patrón de espera orbital,
comunicación FIPA-ACL con TorreAgent y secuencia visual de aterrizaje en 3D.
"""
import math
import random
from collections import deque
from typing import Tuple
from agents.acl import AID, ACLMessage, Performative, DFService
from agents.behaviours import (
    BaseAgent,
    CyclicBehaviour,
    ParallelBehaviour,
    TickerBehaviour,
)
from agents.torre_agent import TorreAgent


PALETA_AEROLINEAS = [
    (235, 75, 75),    # Rojo carmesí
    (65, 165, 245),   # Azul cielo
    (245, 190, 55),   # Dorado
    (80, 220, 145),   # Verde esmeralda
    (215, 110, 245),  # Violeta
    (255, 130, 60),   # Naranja
    (75, 225, 225),   # Turquesa
    (240, 240, 245),  # Blanco perla
    (255, 105, 175),  # Magenta
    (165, 230, 80),   # Lima
]


class AvionTelemetryTicker(TickerBehaviour):
    """Equivalente a TickerBehaviour(this, 1000) de AvionAgent.java."""
    def on_tick(self) -> None:
        avion: AvionAgent = self.my_agent  # type: ignore
        if avion.estado == "VOLANDO":
            print(f"({avion.local_name})")


class AvionVolandoTicker(TickerBehaviour):
    """Equivalente a TickerBehaviour(this, 5000): envía INFORM 'volando' a Torre."""
    def on_tick(self) -> None:
        avion: AvionAgent = self.my_agent  # type: ignore
        if avion.estado != "VOLANDO":
            return
        msg = ACLMessage(performative=Performative.INFORM, content="volando")
        msg.add_receiver(AID("Torre", is_local_name=True))
        avion.send(msg)


class AvionAterrizarTicker(TickerBehaviour):
    """Equivalente a TickerBehaviour(this, 10000): envía PROPOSE 'aterrizar' a Torre."""
    def on_tick(self) -> None:
        avion: AvionAgent = self.my_agent  # type: ignore
        if avion.estado != "VOLANDO":
            return
        msg = ACLMessage(performative=Performative.PROPOSE, content="aterrizar")
        msg.add_receiver(AID("Torre", is_local_name=True))
        avion.send(msg)


class AvionReceiverBehaviour(CyclicBehaviour):
    """Equivalente a CyclicBehaviour de recepción en AvionAgent.java."""
    def action(self, dt: float) -> None:
        avion: AvionAgent = self.my_agent  # type: ignore
        msg = avion.receive()
        if msg is None:
            return

        if msg.content == "recibido":
            if avion.platform:
                avion.platform.log(
                    f"-> {avion.local_name} confirmación de la Torre",
                    (190, 210, 230),
                )
        elif msg.content == "aceptar":
            if avion.estado == "VOLANDO":
                TorreAgent.pista_ocupada = True
                avion.iniciar_aterrizaje()
        elif msg.content == "rechazo":
            avion.rechazos += 1


class AvionAgent(BaseAgent):
    def __init__(self, local_name: str, index: int = 0) -> None:
        super().__init__(local_name)
        self.index = index
        self.color: Tuple[int, int, int] = PALETA_AEROLINEAS[index % len(PALETA_AEROLINEAS)]
        self.estado: str = "VOLANDO"  # VOLANDO | ATERRIZANDO | EN_PISTA
        self.rechazos: int = 0

        # Parámetros de órbita 3D (circuito de espera alrededor del aeropuerto)
        self.orbit_radius: float = 24.0 + (index % 5) * 5.2 + random.uniform(-1.2, 1.2)
        self.orbit_altitude: float = 11.5 + (index % 5) * 2.6
        self.orbit_angle: float = (index * 2.0 * math.pi / 10.0) + random.uniform(-0.2, 0.2)
        self.angular_speed: float = (0.34 - (index % 5) * 0.025) * (1 if index % 2 == 0 else -1)

        # Orientación 3D en radianes
        self.yaw: float = 0.0
        self.pitch: float = 0.0
        self.roll: float = 0.0

        # Variables de animación de aterrizaje (2.6 segundos en tiempo de simulación)
        self.landing_timer: float = 0.0
        self.landing_duration: float = 2.6
        self.landing_start_pos = [0.0, 15.0, -35.0]
        self.trail: deque[Tuple[float, float, float]] = deque(maxlen=26)

        self._update_orbit_transform(0.0)

    def setup(self) -> None:
        DFService.register(self)
        parallel = ParallelBehaviour(self)

        # Desfase inicial escalonado para que las peticiones lleguen progresivamente
        stagger_5s = (self.index * 480) % 4500
        stagger_10s = (self.index * 950) % 8500

        parallel.add_sub_behaviour(AvionTelemetryTicker(self, 1000))
        parallel.add_sub_behaviour(AvionVolandoTicker(self, 5000, initial_delay_ms=stagger_5s))
        parallel.add_sub_behaviour(AvionAterrizarTicker(self, 10000, initial_delay_ms=stagger_10s))
        parallel.add_sub_behaviour(AvionReceiverBehaviour(self))
        self.add_behaviour(parallel)

    def iniciar_aterrizaje(self) -> None:
        self.estado = "ATERRIZANDO"
        self.landing_timer = 0.0
        self.landing_start_pos = list(self.position)
        if self.platform:
            self.platform.log(
                f"=> {self.local_name} (inicio aterrizaje)",
                (255, 225, 95),
            )

    def _update_orbit_transform(self, dt: float) -> None:
        self.orbit_angle += self.angular_speed * dt
        prev_x, prev_y, prev_z = self.position

        x = math.cos(self.orbit_angle) * self.orbit_radius
        z = math.sin(self.orbit_angle) * self.orbit_radius
        y = self.orbit_altitude + math.sin(self.orbit_angle * 2.0 + self.index) * 0.45

        self.position = [x, y, z]
        dx = x - prev_x
        dz = z - prev_z
        if abs(dx) > 1e-6 or abs(dz) > 1e-6:
            self.yaw = math.atan2(dx, dz)
        self.pitch = 0.03
        # Alabeo natural hacia el interior del giro
        self.roll = -0.32 if self.angular_speed > 0 else 0.32

    def _update_landing_transform(self, dt: float) -> None:
        self.landing_timer += dt
        t = min(1.0, self.landing_timer / self.landing_duration)

        # Fase 1 (0.0 -> 0.65): Aproximación final y descenso suave hacia cabecera de pista (0, 0.45, -24)
        # Fase 2 (0.65 -> 1.0): Carrera de aterrizaje y frenado sobre pista hasta (0, 0.35, 26)
        if t < 0.65:
            u = t / 0.65
            ease = u * u * (3.0 - 2.0 * u)
            sx, sy, sz = self.landing_start_pos
            tx, ty, tz = 0.0, 0.42, -22.0
            x = sx + (tx - sx) * ease
            y = sy + (ty - sy) * (u ** 0.85)
            z = sz + (tz - sz) * ease
            dx, dy, dz = tx - x, ty - y, tz - z
            horiz = max(0.1, math.hypot(dx, dz))
            self.yaw = math.atan2(dx, dz) if horiz > 0.2 else 0.0
            self.pitch = max(-0.28, min(0.05, math.atan2(dy, horiz)))
            self.roll *= (1.0 - ease)
            self.position = [x, y, z]
        else:
            self.estado = "EN_PISTA"
            u = (t - 0.65) / 0.35
            ease_out = 1.0 - (1.0 - u) * (1.0 - u)
            z = -22.0 + 48.0 * ease_out
            self.position = [0.0, 0.35, z]
            self.yaw = 0.0
            self.pitch = 0.0
            self.roll = 0.0

        if t >= 1.0:
            if self.platform:
                self.platform.log(
                    f"=> {self.local_name} (fin aterrizaje)",
                    (95, 255, 190),
                )
                self.platform.trigger_sound("touchdown")
                self.platform.total_landed += 1
            TorreAgent.pista_ocupada = False
            self.do_delete()

    def step(self, dt: float) -> None:
        super().step(dt)
        if not self.alive:
            return
        if self.estado == "VOLANDO":
            self._update_orbit_transform(dt)
        else:
            self._update_landing_transform(dt)
        self.trail.append(tuple(self.position))
