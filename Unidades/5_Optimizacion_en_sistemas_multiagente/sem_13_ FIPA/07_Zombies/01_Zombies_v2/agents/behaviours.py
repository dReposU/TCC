"""
Comportamientos JADE: Behaviour, CyclicBehaviour, TickerBehaviour, OneShotBehaviour, ParallelBehaviour.
"""
from collections import deque
from typing import List, Optional
from agents.acl import AID, ACLMessage, DFService, AgentPlatform


class Behaviour:
    def __init__(self, agent: "BaseAgent") -> None:
        self.my_agent = agent
        self._done = False
        self._block_timer: float = 0.0

    def block(self, millis: float) -> None:
        self._block_timer = millis / 1000.0

    def tick_timer(self, dt: float) -> bool:
        if self._block_timer > 0.0:
            self._block_timer -= dt
            return False
        return True

    def action(self, dt: float) -> None:
        raise NotImplementedError

    def done(self) -> bool:
        return self._done


class CyclicBehaviour(Behaviour):
    def done(self) -> bool:
        return False


class OneShotBehaviour(Behaviour):
    def action(self, dt: float) -> None:
        self.on_execute()
        self._done = True

    def on_execute(self) -> None:
        raise NotImplementedError


class TickerBehaviour(Behaviour):
    def __init__(self, agent: "BaseAgent", period_ms: float, initial_delay_ms: Optional[float] = None) -> None:
        super().__init__(agent)
        self.period: float = period_ms / 1000.0
        self.elapsed: float = 0.0 if initial_delay_ms is None else (self.period - initial_delay_ms / 1000.0)

    def action(self, dt: float) -> None:
        if not self.tick_timer(dt):
            return
        self.elapsed += dt
        if self.elapsed >= self.period:
            self.elapsed %= self.period
            self.on_tick()

    def on_tick(self) -> None:
        raise NotImplementedError


class ParallelBehaviour(Behaviour):
    def __init__(self, agent: "BaseAgent") -> None:
        super().__init__(agent)
        self.sub_behaviours: List[Behaviour] = []

    def add_sub_behaviour(self, behaviour: Behaviour) -> None:
        self.sub_behaviours.append(behaviour)

    def action(self, dt: float) -> None:
        active = []
        for sub in self.sub_behaviours:
            sub.action(dt)
            if not sub.done():
                active.append(sub)
        self.sub_behaviours = active

    def done(self) -> bool:
        return len(self.sub_behaviours) == 0


class BaseAgent:
    def __init__(self, local_name: str) -> None:
        self.local_name = local_name
        self.aid = AID(local_name=local_name, is_local_name=True)
        self.platform: Optional[AgentPlatform] = None
        self.mailbox: deque[ACLMessage] = deque()
        self.behaviours: List[Behaviour] = []
        self.alive: bool = True
        self.floor: int = 0
        self.position: List[float] = [0.0, 0.0, 0.0]

    def setup(self) -> None:
        pass

    def add_behaviour(self, behaviour: Behaviour) -> None:
        self.behaviours.append(behaviour)

    def post_message(self, msg: ACLMessage) -> None:
        self.mailbox.append(msg)

    def receive(self) -> Optional[ACLMessage]:
        if self.mailbox:
            return self.mailbox.popleft()
        return None

    def send(self, msg: ACLMessage) -> None:
        msg.sender = self.aid
        if self.platform is not None:
            self.platform.send(msg)

    def do_delete(self) -> None:
        self.alive = False
        DFService.deregister(self)
        if self.platform is not None:
            self.platform.remove_agent(self.local_name)

    def step(self, dt: float) -> None:
        if not self.alive:
            return
        remaining = []
        for b in list(self.behaviours):
            b.action(dt)
            if not b.done() and self.alive:
                remaining.append(b)
        self.behaviours = remaining
