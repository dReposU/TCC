"""
Adaptación de HostAgent.java.
Crea e inicializa el agente Torre y los N agentes Avion_1..Avion_N en la plataforma.
"""
from agents.acl import DFService
from agents.behaviours import BaseAgent
from agents.torre_agent import TorreAgent
from agents.avion_agent import AvionAgent


class HostAgent(BaseAgent):
    numero_aviones: int = 10

    def __init__(self, local_name: str = "Host", numero_aviones: int = 10) -> None:
        super().__init__(local_name)
        HostAgent.numero_aviones = numero_aviones
        self._spawn_counter: int = 0

    def setup(self) -> None:
        DFService.register(self)
        if self.platform is None:
            return

        # 1. Crear agente Torre
        torre = TorreAgent("Torre")
        self.platform.register_agent(torre)

        # 2. Crear agentes avión (Avion_1 .. Avion_10)
        for i in range(HostAgent.numero_aviones):
            self.spawn_avion()

    def spawn_avion(self) -> AvionAgent:
        self._spawn_counter += 1
        local_name = f"Avion_{self._spawn_counter}"
        avion = AvionAgent(local_name=local_name, index=self._spawn_counter - 1)
        if self.platform is not None:
            self.platform.register_agent(avion)
            self.platform.log(
                f"Host: desplegado {local_name} en circuito aéreo",
                (170, 235, 195),
            )
        return avion
