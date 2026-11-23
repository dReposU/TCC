"""
Agente Host: Inicializa la plataforma multi-agente de la universidad,
crea el agente Edificio y despliega N personas y M zombies en los 8 pisos.
"""
from agents.acl import DFService
from agents.behaviours import BaseAgent
from agents.universidad_agent import EdificioAgent
from agents.persona_agent import PersonaAgent
from agents.zombie_agent import ZombieAgent
from agents.medico_agent import MedicoAgent
import random


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

        fuertes_cnt = 0
        debiles_cnt = 0
        for i in range(self.num_personas):
            tipo = "FUERTE" if i % 2 == 0 else "DEBIL"
            if tipo == "FUERTE":
                fuertes_cnt += 1
                name = f"Persona_Fuerte_{fuertes_cnt}"
            else:
                debiles_cnt += 1
                name = f"Persona_Debil_{debiles_cnt}"

            floor, pos, zone = building.sample_person_spawn()
            persona = PersonaAgent(name, floor=floor, spawn_pos=pos, spawn_zone=zone, tipo_humano=tipo)
            self.platform.register_agent(persona)

        self.platform.initial_personas_fuertes = fuertes_cnt
        self.platform.initial_personas_debiles = debiles_cnt

        for _ in range(self.num_zombies):
            z_id = self.platform.next_zombie_id()
            floor, pos, zone = building.sample_zombie_spawn()
            zombie = ZombieAgent(f"Zombie_{z_id}", floor=floor, spawn_pos=pos, spawn_zone=zone, tipo_zombie="NORMAL")
            self.platform.register_agent(zombie)

        # Desplegar Médicos equipados con antídoto en pisos pares (Piso 2, 4, 6, 8 -> índices 1, 3, 5, 7)
        for f in [1, 3, 5, 7]:
            y = building.floors_y[f]
            pos = [random.uniform(-10.0, 10.0), y, random.uniform(-1.0, 1.0)]
            zone = f"P{f+1}_Pasillo"
            medico = MedicoAgent(f"Medico_P{f+1}", floor=f, spawn_pos=pos, spawn_zone=zone, dosis=3)
            self.platform.register_agent(medico)

        self.platform.log(
            f"Host: iniciada simulación N={self.num_personas} ({fuertes_cnt}F/{debiles_cnt}D), M={self.num_zombies} zombies y 4 Médicos en pisos pares (P2, P4, P6, P8)",
            (150, 225, 255),
        )
        self.platform.trigger_sound("alarm_start")
