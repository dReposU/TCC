"""
Implementación ligera del estándar FIPA-ACL y DFService de JADE para Python.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import time


class Performative(str, Enum):
    INFORM = "INFORM"
    PROPOSE = "PROPOSE"
    ACCEPT_PROPOSAL = "ACCEPT_PROPOSAL"
    REJECT_PROPOSAL = "REJECT_PROPOSAL"
    NOT_UNDERSTOOD = "NOT_UNDERSTOOD"


@dataclass(frozen=True)
class AID:
    local_name: str
    is_local_name: bool = True


@dataclass
class ACLMessage:
    performative: Performative
    sender: Optional[AID] = None
    receivers: List[AID] = field(default_factory=list)
    content: str = ""
    timestamp: float = field(default_factory=time.time)

    def add_receiver(self, aid: AID) -> None:
        self.receivers.append(aid)

    def create_reply(self) -> "ACLMessage":
        reply = ACLMessage(performative=Performative.INFORM)
        if self.sender is not None:
            reply.add_receiver(self.sender)
        return reply


@dataclass
class VisualRadioBeam:
    """Representa una transmisión ACL visible en el espacio 3D entre dos agentes."""
    sender_name: str
    receiver_name: str
    performative: Performative
    content: str
    ttl: float = 1.1
    max_ttl: float = 1.1


class DFService:
    """Directory Facilitator (páginas amarillas de agentes JADE)."""
    _registry: Dict[str, "BaseAgent"] = {}

    @classmethod
    def register(cls, agent: "BaseAgent") -> None:
        cls._registry[agent.local_name] = agent

    @classmethod
    def deregister(cls, agent: "BaseAgent") -> None:
        cls._registry.pop(agent.local_name, None)

    @classmethod
    def get_agent(cls, local_name: str) -> Optional["BaseAgent"]:
        return cls._registry.get(local_name)

    @classmethod
    def all_agents(cls) -> List["BaseAgent"]:
        return list(cls._registry.values())

    @classmethod
    def clear(cls) -> None:
        cls._registry.clear()


class AgentPlatform:
    """Contenedor y bus de mensajería para los agentes."""
    def __init__(self) -> None:
        self.agents: Dict[str, "BaseAgent"] = {}
        self.console_logs: List[Tuple[str, str, Tuple[int, int, int]]] = []
        self.radio_beams: List[VisualRadioBeam] = []
        self.sound_events: List[str] = []
        self.total_landed: int = 0
        self.sim_time: float = 0.0

    def reset(self) -> None:
        DFService.clear()
        self.agents.clear()
        self.console_logs.clear()
        self.radio_beams.clear()
        self.sound_events.clear()
        self.total_landed = 0
        self.sim_time = 0.0

    def log(self, text: str, color: Tuple[int, int, int] = (220, 230, 240)) -> None:
        print(text)
        stamp = f"{self.sim_time:05.1f}s"
        self.console_logs.append((stamp, text, color))
        if len(self.console_logs) > 40:
            self.console_logs.pop(0)

    def trigger_sound(self, sound_key: str) -> None:
        self.sound_events.append(sound_key)

    def register_agent(self, agent: "BaseAgent") -> None:
        agent.platform = self
        self.agents[agent.local_name] = agent
        agent.setup()

    def remove_agent(self, local_name: str) -> None:
        agent = self.agents.pop(local_name, None)
        if agent is not None:
            DFService.deregister(agent)

    def send(self, msg: ACLMessage) -> None:
        sender_name = msg.sender.local_name if msg.sender else "Sistema"
        for rec in msg.receivers:
            target = self.agents.get(rec.local_name)
            if target is not None:
                target.post_message(msg)
                self.radio_beams.append(
                    VisualRadioBeam(
                        sender_name=sender_name,
                        receiver_name=rec.local_name,
                        performative=msg.performative,
                        content=msg.content,
                    )
                )

    def step(self, dt: float) -> None:
        self.sim_time += dt
        # Actualizar pulsos visuales de radio 3D
        for beam in self.radio_beams:
            beam.ttl -= dt
        self.radio_beams = [b for b in self.radio_beams if b.ttl > 0.0]

        # Ejecutar ciclo de comportamientos de cada agente activo
        for agent in list(self.agents.values()):
            if agent.alive:
                agent.step(dt)
