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
            tipo_h = msg.data.get("tipo_humano", "")
            tag = f" [{tipo_h}]" if tipo_h else ""
            if edificio.platform:
                edificio.platform.log(
                    f"{edificio.local_name}: {sender_name}{tag} SALVADO por {msg.data.get('salida', 'Salida')}",
                    (95, 250, 155),
                )
        elif msg.content == "transformacion":
            victima = msg.data.get("victima", "Persona")
            tipo_h = msg.data.get("tipo_humano", "HUMANO")
            tipo_z = msg.data.get("tipo_zombie", "ZOMBIE")
            z_creado = msg.data.get("zombie_creado", "Zombie")
            col = (255, 65, 75) if tipo_z == "GRANDE" else (255, 145, 65)
            if edificio.platform:
                edificio.platform.log(
                    f"{edificio.local_name}: {victima} [{tipo_h}] -> TRANSFORMADO en {z_creado} [{tipo_z}]",
                    col,
                )
        elif msg.content == "mordida":
            victima = msg.data.get("victima", "Persona")
            tipo_h = msg.data.get("tipo_humano", "Humano")
            if edificio.platform:
                edificio.platform.log(
                    f"{edificio.local_name}: ALERTA {sender_name} atrapó a {victima} [{tipo_h}]",
                    (255, 95, 95),
                )
        elif msg.content == "cura_exitosa":
            medico = msg.data.get("medico", "Médico")
            victima = msg.data.get("zombie_curado", "Zombie")
            restaurado = msg.data.get("humano_restaurado", "Humano")
            tipo_h = msg.data.get("tipo_humano", "HUMANO")
            tipo_z = msg.data.get("tipo_zombie", "NORMAL")
            dosis = msg.data.get("dosis_usadas", 1)
            if edificio.platform:
                edificio.platform.log(
                    f"{edificio.local_name}: {medico} CURÓ a {victima} [{tipo_z}] ({dosis} dosis) -> Revertido a {restaurado} [{tipo_h}]",
                    (70, 245, 220),
                )
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
