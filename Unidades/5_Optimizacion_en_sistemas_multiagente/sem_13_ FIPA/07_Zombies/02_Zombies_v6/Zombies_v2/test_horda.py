"""
Pruebas automáticas (sin ventana) de la caza coordinada "horda" y del fix de atasco en puertas.

Uso:
    python test_horda.py

No necesita pygame: solo ejecuta la lógica de agentes.
"""
import math
import random

from agents.acl import AgentPlatform, Performative
from agents.host_agent import HostAgent
from agents.persona_agent import PersonaAgent
from agents.universidad_agent import EdificioAgent
from agents.zombie_agent import ZombieAgent, RADIO_COMUNICACION
from world.university import UniversityBuilding

DT = 0.02


def nueva_plataforma():
    b = UniversityBuilding()
    p = AgentPlatform(b)
    p.register_agent(EdificioAgent("Edificio"))
    return b, p


def espiar_mensajes(p):
    """Envuelve platform.send para registrar los INFORM presa_detectada."""
    enviados = []
    original = p.send

    def spy(msg):
        if msg.content == "presa_detectada":
            enviados.append(msg)
        original(msg)

    p.send = spy
    return enviados


def test_inform_radio_y_pisos_adyacentes():
    """El zombie que detecta una presa avisa SOLO a los zombies dentro de 12 m (3D),
    incluidos los de pisos adyacentes, y estos pasan a modo emboscada."""
    b, p = nueva_plataforma()
    enviados = espiar_mensajes(p)
    y = b.floors_y
    piso = 3

    cazador = ZombieAgent("Z_cazador", piso, [0.0, y[piso], 0.0], "test")
    cerca = ZombieAgent("Z_cerca", piso, [9.0, y[piso], 0.0], "test")           # 9 m, mismo piso
    arriba = ZombieAgent("Z_arriba", piso + 1, [5.0, y[piso + 1], 0.0], "test")  # ~6.8 m (3D), piso adyacente
    lejos = ZombieAgent("Z_lejos", piso, [-16.0, y[piso], 6.0], "test")          # >12 m
    dos_pisos = ZombieAgent("Z_2pisos", piso + 2, [0.5, y[piso + 2], 0.0], "test")  # 9.2 m pero 2 pisos
    for z in (cazador, cerca, arriba, lejos, dos_pisos):
        p.register_agent(z)

    # Presa a 4 m del cazador -> fuera de la visión de "lejos"
    presa = PersonaAgent("Presa", piso, [3.0, y[piso], 1.5], "test")
    p.register_agent(presa)
    cerca.vision_radius = arriba.vision_radius = lejos.vision_radius = 0.0  # que solo se enteren por ACL
    dos_pisos.vision_radius = 0.0

    p.step(DT)
    p.step(DT)

    assert cazador.chasing, "el cazador debería estar persiguiendo"
    assert len(enviados) == 1, f"se esperaba 1 INFORM, hubo {len(enviados)}"
    msg = enviados[0]
    assert msg.performative == Performative.INFORM
    receptores = {r.local_name for r in msg.receivers}
    assert receptores == {"Z_cerca", "Z_arriba"}, f"receptores incorrectos: {receptores}"
    for z in (cerca, arriba):
        d = cazador._distancia_3d(z)
        assert d <= RADIO_COMUNICACION, f"{z.local_name} fuera de radio ({d:.1f} m)"
        assert z.emboscada is not None, f"{z.local_name} no entró en emboscada"
    assert lejos.emboscada is None and dos_pisos.emboscada is None
    # Se reparten salidas distintas
    assert cerca.emboscada["salida"] != arriba.emboscada["salida"], "dos receptores con la misma salida"
    print("OK  INFORM presa_detectada: radio 12 m, pisos adyacentes, salidas repartidas")
    return p, arriba, piso


def test_cambio_de_piso():
    """El zombie del piso adyacente baja por la escalera y llega al punto de emboscada."""
    p, arriba, piso = test_inform_radio_y_pisos_adyacentes()
    presa = p.agents["Presa"]
    presa.walk_speed = presa.run_speed = 0.0   # congelar la presa para que la emboscada no expire
    cazador = p.agents["Z_cazador"]
    cazador.chase_speed = 0.0                  # que el cazador no la muerda (cancelaría la emboscada)
    cazador.position[0] = presa.position[0] - 3.0
    for _ in range(int(8.0 / DT)):
        p.step(DT)
        if arriba.floor == piso and arriba.emboscada is not None:
            px, pz = arriba.emboscada["punto"]
            if math.hypot(px - arriba.position[0], pz - arriba.position[2]) < 1.0:
                break
    assert arriba.floor == piso, "el zombie del piso adyacente no bajó"
    assert abs(arriba.position[1] - p.building.floors_y[piso]) < 1e-6
    print("OK  Zombie de piso adyacente usa la escalera y llega a su salida")


def test_modo_horda_off():
    """Con modo_horda = False no se envían avisos (comportamiento original)."""
    b, p = nueva_plataforma()
    p.modo_horda = False
    enviados = espiar_mensajes(p)
    y = b.floors_y
    a = ZombieAgent("Z_a", 0, [0.0, y[0], 0.0], "test")
    c = ZombieAgent("Z_b", 0, [5.0, y[0], 0.0], "test")
    p.register_agent(a)
    p.register_agent(c)
    p.register_agent(PersonaAgent("Presa", 0, [3.0, y[0], 1.0], "test"))
    for _ in range(10):
        p.step(DT)
    assert not enviados and c.emboscada is None
    print("OK  Modo horda OFF: no hay INFORM ni emboscadas")


def test_no_atasco_en_puertas():
    """Un zombie en el pasillo con la presa dentro de un aula debe entrar (antes se congelaba en la puerta)."""
    b, p = nueva_plataforma()
    y = b.floors_y
    z = ZombieAgent("Z", 0, [8.5, y[0], 0.0], "test")              # pasillo, frente a Aula_4
    p.register_agent(z)
    presa = PersonaAgent("Presa", 0, [8.5, y[0], 6.5], "test")     # dentro de P1_Aula_4
    p.register_agent(presa)
    presa.walk_speed = presa.run_speed = 0.0                       # inmóvil para aislar el caso
    for _ in range(int(5.0 / DT)):
        p.step(DT)
        if presa.estado != "SANO":
            break
    assert presa.estado == "INFECTADO", f"el zombie no llegó a la presa; quedó en {z.position}"
    print("OK  Fix puertas: el zombie entra al aula y alcanza a la presa")


def test_simulacion_completa():
    """Simulación completa (N=32, M=12) durante 60 s: sin errores, con avisos y sin zombies congelados."""
    random.seed(7)
    b = UniversityBuilding()
    p = AgentPlatform(b)
    p.register_agent(HostAgent("Host", 32, 12))
    ult = {}
    congelados = 0
    max_emb = 0
    for i in range(int(60.0 / DT)):
        p.step(DT)
        zs = [a for a in p.agents.values() if isinstance(a, ZombieAgent)]
        max_emb = max(max_emb, sum(1 for z in zs if z.emboscada))
        if i % 100 == 0:  # cada 2 s
            for z in zs:
                prev = ult.get(z.local_name)
                if prev and z.chasing and math.hypot(z.position[0] - prev[0], z.position[2] - prev[1]) < 0.05:
                    congelados += 1
                ult[z.local_name] = (z.position[0], z.position[2])
    print(
        f"OK  Simulación 60 s: salvados={p.total_salvados} infectados={p.total_infectados} "
        f"avisos={p.total_avisos_horda} max_emboscando={max_emb} "
        f"infectados_por_emboscada={p.infectados_por_horda} zombies_congelados={congelados}"
    )
    assert p.total_avisos_horda > 0
    assert congelados <= 2, f"hay zombies persiguiendo pero congelados ({congelados})"


if __name__ == "__main__":
    test_cambio_de_piso()
    test_modo_horda_off()
    test_no_atasco_en_puertas()
    test_simulacion_completa()
    print("\nTodas las pruebas pasaron.")
