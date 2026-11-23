"""
Adaptación de TorreAgent.java al entorno Multi-Agente en Python/PyGame 3D.
Gestiona el acceso exclusivo a la pista de aterrizaje (pista_ocupada).
"""
from typing import Optional
from agents.acl import ACLMessage, Performative, DFService
from agents.behaviours import BaseAgent, CyclicBehaviour


class TorreControlBehaviour(CyclicBehaviour):
    def action(self, dt: float) -> None:
        torre: TorreAgent = self.my_agent  # type: ignore
        msg = torre.receive()
        if msg is None:
            return

        sender_name = msg.sender.local_name if msg.sender else "Desconocido"
        if torre.platform:
            torre.platform.log(
                f"{torre.local_name}: reporte de {sender_name} [{msg.content}]",
                (140, 210, 255),
            )

        reply = msg.create_reply()
        if msg.content == "volando":
            reply.performative = Performative.INFORM
            reply.content = "recibido"
            if torre.platform:
                torre.platform.trigger_sound("radio_ping")

        elif msg.content == "aterrizar":
            if TorreAgent.pista_ocupada:
                reply.performative = Performative.REJECT_PROPOSAL
                reply.content = "rechazo"
                if torre.platform:
                    torre.platform.log(
                        f"{torre.local_name}: rechazo a {sender_name} (pista ocupada por {torre.avion_en_pista})",
                        (255, 115, 115),
                    )
                    torre.platform.trigger_sound("landing_reject")
            else:
                TorreAgent.pista_ocupada = True
                torre.avion_en_pista = sender_name
                reply.performative = Performative.ACCEPT_PROPOSAL
                reply.content = "aceptar"
                if torre.platform:
                    torre.platform.log(
                        f"{torre.local_name}: permiso para {sender_name}",
                        (110, 255, 150),
                    )
                    torre.platform.trigger_sound("landing_accept")
        else:
            reply.performative = Performative.NOT_UNDERSTOOD
            reply.content = "desconocido"

        torre.send(reply)


class TorreAgent(BaseAgent):
    pista_ocupada: bool = False

    def __init__(self, local_name: str = "Torre") -> None:
        super().__init__(local_name)
        TorreAgent.pista_ocupada = False
        self.avion_en_pista: Optional[str] = None
        # Ubicación 3D junto a la pista de aterrizaje
        self.position = [-11.5, 0.0, -3.0]
        self.radar_angle: float = 0.0

    def setup(self) -> None:
        DFService.register(self)
        self.add_behaviour(TorreControlBehaviour(self))

    def step(self, dt: float) -> None:
        super().step(dt)
        self.radar_angle = (self.radar_angle + dt * 1.8) % 6.2831853
        if not TorreAgent.pista_ocupada:
            self.avion_en_pista = None
