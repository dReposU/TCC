"""
[NUEVO] Agente Brigadista: 1 por piso, desplegado por HostAgent.

ROL
---
Rescatista con más velocidad y más visión (18 m) que las personas.
Llama con REQUEST "siganme" a las personas que siguen dentro de las 4 aulas
de su piso, las recoge al tocarlas y las guía EN FILA (por su misma ruta)
hacia la salida de emergencia más segura.

REGLAS DEL CASO
---------------
- Al tocar a una persona (<= CONTACTO m) esta se une al grupo: adopta la
  velocidad del brigadista y pisa su misma ruta (breadcrumbs).
- Capacidad mínima: solo va a la salida con >= MIN_GRUPO personas, salvo que
  ya no quede nadie más por recoger en su piso (evita un deadlock).
- Puede ser mordido: si lo muerden, TODO su grupo se infecta (cascada).

MÁQUINA DE ESTADOS
------------------
RECOLECTANDO --(grupo >= MIN o no quedan pendientes)--> GUIANDO
GUIANDO --(llega a la salida)--> EN_SALIDA
EN_SALIDA --(todo el grupo salió)--> RECOLECTANDO (si quedan personas) | RETIRANDO
RETIRANDO --(llega a una salida)--> SALVADO (se elimina)
cualquiera --(mordida)--> INFECTADO (se elimina + su grupo se infecta)
"""
import math
import random
from collections import deque
from typing import List, Optional, Tuple
from agents.acl import AID, ACLMessage, Performative, DFService
from agents.behaviours import BaseAgent, CyclicBehaviour, ParallelBehaviour, TickerBehaviour

MIN_GRUPO = 2          # capacidad mínima para dirigirse a la salida
CONTACTO = 1.5         # distancia (m) a la que "toca" a una persona y la une al grupo
SEPARACION_RUTA = 0.3  # cada cuántos metros guarda un punto de su ruta (breadcrumb)
PUNTOS_POR_PUESTO = 4  # 4 puntos * 0.3 m = 1.2 m de separación entre personas en la fila


def _dist(a: List[float], b: List[float]) -> float:
    """Distancia horizontal (x, z) entre dos posiciones."""
    return math.hypot(a[0] - b[0], a[2] - b[2])


class BrigadistaLlamadoTicker(TickerBehaviour):
    """Cada 2 s: REQUEST "siganme" a personas sanas dentro de un aula de su piso y en su visión."""
    def on_tick(self) -> None:
        b: BrigadistaAgent = self.my_agent  # type: ignore
        if b.platform is None or b.estado not in ("RECOLECTANDO", "GUIANDO"):
            return
        building = b.platform.building
        for p in b.personas_del_piso():
            if p.modo != "LIBRE" or p.local_name in b.llamados:
                continue  # ya fue llamada o ya sigue a alguien
            en_aula = building.get_room_containing(b.floor, p.position) is not None
            if en_aula and _dist(p.position, b.position) <= b.vision_radius:
                msg = ACLMessage(
                    performative=Performative.REQUEST,
                    content="siganme",
                    data={"lider": b.local_name},
                )
                msg.add_receiver(p.aid)
                b.send(msg)
                b.llamados.add(p.local_name)


class BrigadistaReceiverBehaviour(CyclicBehaviour):
    """Procesa las respuestas de las personas (AGREE = aceptó el llamado)."""
    def action(self, dt: float) -> None:
        b: BrigadistaAgent = self.my_agent  # type: ignore
        msg = b.receive()
        if msg is None:
            return
        if msg.performative == Performative.AGREE and b.platform:
            b.platform.log(f"{b.local_name}: {msg.sender.local_name} acepta seguirlo", (255, 190, 90))


class BrigadistaMoverBehaviour(CyclicBehaviour):
    """Decide hacia dónde ir según su estado, recoge personas por contacto y se mueve."""
    def action(self, dt: float) -> None:
        b: BrigadistaAgent = self.my_agent  # type: ignore
        if b.platform is None or not b.alive:
            return
        building = b.platform.building

        # 1) Limpiar el grupo: quitar a los que ya se salvaron, murieron o se infectaron
        b.grupo = [n for n in b.grupo if b._persona_viva(n)]

        # 2) Contacto: toda persona llamada (o en aula) que esté a <= CONTACTO se une al grupo
        if b.estado in ("RECOLECTANDO", "GUIANDO"):
            for p in b.personas_del_piso():
                if p.modo == "SIGUIENDO" or p.local_name in b.grupo:
                    continue
                llamada_o_en_aula = p.modo == "LLAMADA" or building.get_room_containing(b.floor, p.position)
                if llamada_o_en_aula and _dist(p.position, b.position) <= CONTACTO:
                    b.unir(p)

        pendientes = b.pendientes()  # personas que aún hay que recoger en este piso

        # 3) Transiciones de estado
        if b.estado == "RECOLECTANDO":
            # Capacidad mínima: sale con >= MIN_GRUPO, o con lo que tenga si ya no queda nadie
            if len(b.grupo) >= MIN_GRUPO or (b.grupo and not pendientes):
                b.estado = "GUIANDO"
                b.salida = b.elegir_salida_segura()
                b.platform.log(
                    f"{b.local_name}: guiando {len(b.grupo)} personas a {b.salida.name}", (255, 170, 60)
                )
            elif not b.grupo and not pendientes:
                b.estado = "RETIRANDO"  # ya no queda nadie en las aulas: sale él también
                b.salida = b.elegir_salida_segura()
        elif b.estado == "GUIANDO":
            b.salida = b.elegir_salida_segura()  # se recalcula: la salida "segura" cambia si llegan zombies
            if _dist(b.position, list(b.salida.center)) <= 1.25:
                b.estado = "EN_SALIDA"  # se detiene en la puerta y deja pasar a su grupo
                msg = ACLMessage(
                    performative=Performative.INFORM,
                    content="grupo_en_salida",
                    data={"salida": b.salida.name, "personas": len(b.grupo)},
                )
                msg.add_receiver(AID("Edificio", is_local_name=True))
                b.send(msg)
        elif b.estado == "EN_SALIDA":
            if not b.grupo:  # todos salieron: vuelve por más o se retira
                b.estado = "RECOLECTANDO" if pendientes else "RETIRANDO"
                b.salida = b.elegir_salida_segura()
            return  # quieto en la salida
        elif b.estado == "RETIRANDO":
            if _dist(b.position, list(b.salida.center)) <= 1.25:
                b.salvar()
                return

        # 4) Elegir el punto objetivo
        if b.estado == "RECOLECTANDO":
            objetivo = min(pendientes, key=lambda p: _dist(p.position, b.position), default=None)
            if objetivo is None:
                return
            tx, tz = b.navegar_hacia(objetivo.position)
        else:  # GUIANDO / RETIRANDO
            tx, tz = b.navegar_hacia(list(b.salida.center))

        # 5) Moverse hacia el objetivo esquivando zombies cercanos (igual que la persona)
        dx, dz = tx - b.position[0], tz - b.position[2]
        d = max(1e-5, math.hypot(dx, dz))
        vx, vz = dx / d, dz / d
        z = b.zombie_mas_cercano()
        if z is not None:
            dzm = _dist(z.position, b.position)
            if dzm < 6.0:
                ax, az = b.position[0] - z.position[0], b.position[2] - z.position[2]
                al = max(1e-5, math.hypot(ax, az))
                w = (6.0 - dzm) / 6.0 * 1.2
                vx, vz = vx + ax / al * w, vz + az / al * w
                n = max(1e-5, math.hypot(vx, vz))
                vx, vz = vx / n, vz / n
        paso = min(d, b.speed * dt)
        b.position[0] = max(-17.6, min(17.6, b.position[0] + vx * paso))
        b.position[2] = max(-7.6, min(7.6, b.position[2] + vz * paso))
        b.yaw = math.atan2(vx, vz)
        b.walk_phase += dt * b.speed * 3.4

        # 6) Guardar la ruta (breadcrumbs) que pisarán sus seguidores
        if _dist(b.position, list(b.ruta[-1])) >= SEPARACION_RUTA:
            b.ruta.append(tuple(b.position))


class BrigadistaAgent(BaseAgent):
    def __init__(self, local_name: str, floor: int, spawn_pos: List[float]) -> None:
        super().__init__(local_name)
        self.floor = floor
        self.position = list(spawn_pos)
        self.speed: float = 5.0          # más rápido que una persona corriendo (3.9 - 4.6)
        self.vision_radius: float = 18.0  # más visión que un zombie (14.5)
        self.estado: str = "RECOLECTANDO"
        self.grupo: List[str] = []        # nombres de los seguidores, en orden de fila
        self.llamados: set = set()        # personas a las que ya se envió REQUEST
        self.salida = None
        self.ruta: deque = deque([tuple(self.position)], maxlen=400)  # breadcrumbs
        self.yaw: float = 0.0
        self.walk_phase: float = 0.0
        self.color: Tuple[int, int, int] = (255, 140, 0)  # naranja chaleco

    def setup(self) -> None:
        DFService.register(self)
        parallel = ParallelBehaviour(self)
        parallel.add_sub_behaviour(BrigadistaLlamadoTicker(self, 2000, initial_delay_ms=random.uniform(200, 800)))
        parallel.add_sub_behaviour(BrigadistaReceiverBehaviour(self))
        parallel.add_sub_behaviour(BrigadistaMoverBehaviour(self))
        self.add_behaviour(parallel)

    # ---------------- percepción ----------------
    def personas_del_piso(self):
        from agents.persona_agent import PersonaAgent
        return [a for a in self.platform.agents.values()
                if isinstance(a, PersonaAgent) and a.alive and a.estado == "SANO" and a.floor == self.floor]

    def pendientes(self):
        """Personas aún por recoger: llamadas, o dentro de un aula y sin líder."""
        building = self.platform.building
        return [p for p in self.personas_del_piso()
                if p.local_name not in self.grupo and p.modo != "SIGUIENDO"
                and (p.modo == "LLAMADA" or building.get_room_containing(self.floor, p.position) is not None)]

    def zombie_mas_cercano(self):
        from agents.zombie_agent import ZombieAgent
        zs = [a for a in self.platform.agents.values()
              if isinstance(a, ZombieAgent) and a.alive and a.floor == self.floor]
        return min(zs, key=lambda z: _dist(z.position, self.position), default=None)

    def _persona_viva(self, nombre: str) -> bool:
        p = self.platform.agents.get(nombre)
        return p is not None and p.alive and getattr(p, "estado", "") == "SANO"

    # ---------------- decisiones ----------------
    def elegir_salida_segura(self):
        """Salida con menor costo = distancia + penalización por zombies cerca (reutiliza la fórmula de PersonaAgent)."""
        from agents.zombie_agent import ZombieAgent
        zs = [a for a in self.platform.agents.values()
              if isinstance(a, ZombieAgent) and a.alive and a.floor == self.floor]
        mejor, mejor_costo = None, 1e9
        for ex in self.platform.building.exits[self.floor]:
            costo = _dist(list(ex.center), self.position)
            for z in zs:
                d = _dist(z.position, list(ex.center))
                if d < 6.0:  # radio de riesgo mayor que el de la persona (4.5): ve más lejos
                    costo += (6.0 - d) * 8.0
            if costo < mejor_costo:
                mejor, mejor_costo = ex, costo
        return mejor

    def navegar_hacia(self, destino: List[float]) -> Tuple[float, float]:
        """Ruta por puertas: si destino y brigadista están en zonas distintas, pasa por la puerta del aula."""
        building = self.platform.building
        mi_aula = building.get_room_containing(self.floor, self.position)
        su_aula = building.get_room_containing(self.floor, destino)
        if mi_aula == su_aula:
            return destino[0], destino[2]
        puerta = (mi_aula or su_aula).door_pos
        # Ya en la puerta -> seguir directo al destino (si no, se quedaría parado en la puerta)
        if math.hypot(puerta[0] - self.position[0], puerta[2] - self.position[2]) < 1.0:
            return destino[0], destino[2]
        return puerta[0], puerta[2]

    # ---------------- acciones ----------------
    def unir(self, persona) -> None:
        """La persona tocada se une al grupo: se le asigna su puesto en la fila."""
        self.grupo.append(persona.local_name)
        msg = ACLMessage(
            performative=Performative.INFORM,
            content="unido",
            data={"lider": self.local_name, "slot": len(self.grupo) - 1},
        )
        msg.add_receiver(persona.aid)
        self.send(msg)
        persona.unirse_a(self, len(self.grupo) - 1)  # contacto físico: efecto inmediato
        if self.platform:
            self.platform.log(f"{self.local_name}: {persona.local_name} se une ({len(self.grupo)})", (255, 200, 90))

    def punto_de_fila(self, slot: int) -> List[float]:
        """Punto de su ruta que le toca pisar al seguidor 'slot' (más atrás cuanto mayor el slot)."""
        idx = len(self.ruta) - 1 - PUNTOS_POR_PUESTO * (slot + 1)
        x, y, z = self.ruta[max(0, idx)]
        return [x, y, z]

    def infectar(self, attacker_name: str) -> None:
        """Mordido: él se convierte en zombie y TODO su grupo se infecta (cascada)."""
        if self.estado == "INFECTADO" or self.platform is None:
            return
        self.estado = "INFECTADO"
        grupo = list(self.grupo)
        msg = ACLMessage(
            performative=Performative.ALERT,
            content="brigadista_mordido",
            data={"atacante": attacker_name, "grupo": len(grupo), "piso": self.floor + 1},
        )
        msg.add_receiver(AID("Edificio", is_local_name=True))
        self.send(msg)
        self.platform.brigadistas_caidos += 1
        self.platform.spawn_effect(self.position, (255, 70, 70), "BRIGADISTA CAÍDO!")
        self.platform.trigger_sound("alert_bite")

        # Cascada: cada seguidor se infecta (y PersonaAgent.infectar ya crea su zombie)
        for nombre in grupo:
            p = self.platform.agents.get(nombre)
            if p is not None and p.alive:
                p.infectar(self.local_name)

        # El brigadista también se convierte en zombie
        from agents.zombie_agent import ZombieAgent
        z = ZombieAgent(
            local_name=f"Zombie_Inf_{self.platform.next_zombie_id()}",
            floor=self.floor,
            spawn_pos=list(self.position),
            spawn_zone=f"P{self.floor+1}_Infeccion",
            is_converted=True,
        )
        self.platform.register_agent(z)
        self.do_delete()

    def salvar(self) -> None:
        """Ya no quedan personas en las aulas de su piso: sale del edificio."""
        self.estado = "SALVADO"
        if self.platform:
            msg = ACLMessage(performative=Performative.INFORM, content="brigadista_fuera",
                             data={"salida": self.salida.name})
            msg.add_receiver(AID("Edificio", is_local_name=True))
            self.send(msg)
            self.platform.spawn_effect(self.position, (255, 170, 60), "PISO DESPEJADO")
        self.do_delete()
