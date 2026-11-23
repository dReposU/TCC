"""
Infraestructura FIPA-ACL, Directory Facilitator (DFService) y Plataforma Multi-Agente.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import time


class Performative(str, Enum):
    INFORM = "INFORM"
    REQUEST = "REQUEST"
    ALERT = "ALERT"
    CONFIRM = "CONFIRM"
    PROPOSE = "PROPOSE"
    ACCEPT_PROPOSAL = "ACCEPT_PROPOSAL"
    REJECT_PROPOSAL = "REJECT_PROPOSAL"


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
    data: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def add_receiver(self, aid: AID) -> None:
        self.receivers.append(aid)

    def create_reply(self, performative: Performative = Performative.CONFIRM) -> "ACLMessage":
        reply = ACLMessage(performative=performative)
        if self.sender is not None:
            reply.add_receiver(self.sender)
        return reply


@dataclass
class VisualRadioBeam:
    sender_name: str
    receiver_name: str
    performative: Performative
    content: str
    ttl: float = 0.85
    max_ttl: float = 0.85


@dataclass
class VisualEffect3D:
    position: List[float]
    color: Tuple[int, int, int]
    label: str
    ttl: float = 1.2
    max_ttl: float = 1.2


class DFService:
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
    def __init__(self, building) -> None:
        self.building = building
        self.agents: Dict[str, "BaseAgent"] = {}
        self.console_logs: List[Tuple[str, str, Tuple[int, int, int]]] = []
        self.radio_beams: List[VisualRadioBeam] = []
        self.effects_3d: List[VisualEffect3D] = []
        self.sound_events: List[str] = []

        self.initial_personas: int = 0
        self.initial_zombies: int = 0
        self.total_salvados: int = 0
        self.total_infectados: int = 0
        self.sim_time: float = 0.0
        self._zombie_seq: int = 0

    def reset(self, building) -> None:
        DFService.clear()
        self.building = building
        self.agents.clear()
        self.console_logs.clear()
        self.radio_beams.clear()
        self.effects_3d.clear()
        self.sound_events.clear()
        self.initial_personas = 0
        self.initial_zombies = 0
        self.total_salvados = 0
        self.total_infectados = 0
        self.sim_time = 0.0
        self._zombie_seq = 0

    def next_zombie_id(self) -> int:
        self._zombie_seq += 1
        return self._zombie_seq

    def log(self, text: str, color: Tuple[int, int, int] = (215, 228, 240)) -> None:
        stamp = f"{self.sim_time:05.1f}s"
        self.console_logs.append((stamp, text, color))
        if len(self.console_logs) > 50:
            self.console_logs.pop(0)

    def trigger_sound(self, key: str) -> None:
        self.sound_events.append(key)

    def spawn_effect(self, pos: List[float], color: Tuple[int, int, int], label: str) -> None:
        self.effects_3d.append(VisualEffect3D(position=list(pos), color=color, label=label))

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
            if target is not None and target.alive:
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
        for beam in self.radio_beams:
            beam.ttl -= dt
        self.radio_beams = [b for b in self.radio_beams if b.ttl > 0.0]

        for eff in self.effects_3d:
            eff.ttl -= dt
            eff.position[1] += dt * 1.1
        self.effects_3d = [e for e in self.effects_3d if e.ttl > 0.0]

        for agent in list(self.agents.values()):
            if agent.alive:
                agent.step(dt)