"""
Agente Host: Inicializa la plataforma multi-agente de la universidad,
crea el agente Edificio y despliega N personas y M zombies en los 8 pisos.
"""
from agents.acl import DFService
from agents.behaviours import BaseAgent
from agents.universidad_agent import EdificioAgent
from agents.persona_agent import PersonaAgent
from agents.zombie_agent import ZombieAgent
from agents.brigadista_agent import BrigadistaAgent  # [MOD]


class HostAgent(BaseAgent):
    def __init__(self, local_name: str = "Host", num_personas: int = 32, num_zombies: int = 12) -> None:
        super().__init__(local_name)
        self.num_personas = num_personas
        self.num_zombies = num_zombies
        self.floor = 7
        self.position = [0.0, 38.5, 0.0]

    def setup(self) -> None:
        DFService.register(self)
        if self.platform is None:
            return

        building = self.platform.building
        self.platform.initial_personas = self.num_personas
        self.platform.initial_zombies = self.num_zombies

        edificio = EdificioAgent("Edificio")
        self.platform.register_agent(edificio)

        for i in range(self.num_personas):
            floor, pos, zone = building.sample_person_spawn()
            persona = PersonaAgent(f"Persona_{i+1}", floor=floor, spawn_pos=pos, spawn_zone=zone)
            self.platform.register_agent(persona)

        for _ in range(self.num_zombies):
            z_id = self.platform.next_zombie_id()
            floor, pos, zone = building.sample_zombie_spawn()
            zombie = ZombieAgent(f"Zombie_{z_id}", floor=floor, spawn_pos=pos, spawn_zone=zone)
            self.platform.register_agent(zombie)

        # [MOD] Un brigadista por piso, en el centro del pasillo
        for f in range(building.NUM_FLOORS):
            brig = BrigadistaAgent(f"Brigadista_P{f+1}", floor=f, spawn_pos=[0.0, building.floors_y[f], 0.0])
            self.platform.register_agent(brig)

        self.platform.log(
            f"Host: iniciada simulación con N={self.num_personas} personas y M={self.num_zombies} zombies en 8 pisos",
            (150, 225, 255),
        )
        self.platform.trigger_sound("alarm_start")
