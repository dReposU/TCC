"""
Agente coordinador de la Universidad (Edificio de 8 pisos).
Recibe reportes FIPA-ACL de personas y zombies, y contabiliza salvados e infectados.
"""
from agents.acl import Performative, DFService
from agents.behaviours import BaseAgent, CyclicBehaviour


class EdificioMonitorBehaviour(CyclicBehaviour):
    def action(self, dt: float) -> None:
        edificio: EdificioAgent = self.my_agent  # type: ignore
        msg = edificio.receive()
        if msg is None:
            return

        sender_name = msg.sender.local_name if msg.sender else "Desconocido"
        if msg.content == "salvado":
            if edificio.platform:
                edificio.platform.log(
                    f"{edificio.local_name}: {sender_name} SALVADO por {msg.data.get('salida', 'Salida')}",
                    (95, 250, 155),
                )
        elif msg.content == "mordida":
            victima = msg.data.get("victima", "Persona")
            if edificio.platform:
                edificio.platform.log(
                    f"{edificio.local_name}: ALERTA {sender_name} infectó a {victima}",
                    (255, 95, 95),
                )
        # [MOD] Reportes de los brigadistas
        elif msg.content == "grupo_en_salida":
            if edificio.platform:
                edificio.platform.log(
                    f"{edificio.local_name}: {sender_name} llegó a {msg.data.get('salida')} con {msg.data.get('personas')} personas",
                    (255, 185, 80),
                )
        elif msg.content == "brigadista_mordido":
            if edificio.platform:
                edificio.platform.log(
                    f"{edificio.local_name}: ALERTA {sender_name} mordido, {msg.data.get('grupo')} seguidores infectados",
                    (255, 60, 60),
                )
        elif msg.content == "brigadista_fuera":
            if edificio.platform:
                edificio.platform.log(f"{edificio.local_name}: {sender_name} despejó su piso y salió", (255, 185, 80))
        elif msg.content == "evacuando":
            reply = msg.create_reply(Performative.CONFIRM)
            reply.content = "ruta_despejada"
            edificio.send(reply)


class EdificioAgent(BaseAgent):
    def __init__(self, local_name: str = "Edificio") -> None:
        super().__init__(local_name)
        self.floor = 0
        self.position = [0.0, 38.5, 0.0]

    def setup(self) -> None:
        DFService.register(self)
        self.add_behaviour(EdificioMonitorBehaviour(self))
