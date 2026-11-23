# Simulación Multi-Agente 3D: Invasión Zombie en la Universidad

Simulación 3D interactiva desarrollada en **Python + PyGame + NumPy** con arquitectura de agentes basada en comportamientos (`CyclicBehaviour`, `TickerBehaviour`, `ParallelBehaviour`) y mensajería FIPA-ACL (`INFORM`, `ALERT`, `CONFIRM`).

## Escenario Modelado
- **Edificio Universitario**: 8 pisos (`Piso 1` a `Piso 8`).
- **Distribución por piso**: 4 aulas (`Aula_1` a `Aula_4`), 1 pasillo central y 3 salidas de emergencia (`Salida_1`, `Salida_2`, `Salida_3`).
- **Agentes**:
  - `HostAgent`: Inicializa la plataforma y despliega `N` personas y `M` zombies.
  - `EdificioAgent`: Coordina reportes ACL y contabiliza cuántos se salvan y cuántos se infectan.
  - `PersonaAgent`: Evacúa desde las aulas/pasillos hacia las salidas de emergencia evitando zombies cercanos. Presenta dos tipos de humanos:
    - **Humano Fuerte**: Mayor velocidad de carrera (`4.7 - 5.4`), menor tiempo de pánico (`1.2s`), mayor porte físico (`escala 1.08x`) y vestimenta atlética. **Al ser atrapado se transforma en un Zombie Grande.**
    - **Humano Débil**: Velocidad moderada (`3.5 - 4.1`), mayor susceptibilidad al pánico (`2.8s`), contextura esbelta (`escala 0.88x`) y colores pastel. **Al ser atrapado se transforma en un Zombie Normal.**
  - `ZombieAgent`: Patrulla salones (45%), pasillos (45%) y salidas de emergencia (10%), persigue personas y las transforma al morder:
    - **Zombie Grande**: Producto de la transformación de un humano fuerte. Tamaño colosal (`escala 1.45x`), mayor alcance de mordida (`1.45m`), radio de visión extendido (`16.5m`) y rugido de alerta más amplio (`11.5m`).
    - **Zombie Normal**: Tamaño estándar (`escala 0.92x`), radio de visión de `14.5m` y alcance de mordida de `1.15m`.
  - `MedicoAgent`: Desplegado en **pisos pares** (Pisos 2, 4, 6 y 8) con **3 dosis de antídoto** cada uno.
    - Intercepta zombies recién infectados (`is_converted == True`) y envía mensaje FIPA-ACL `REQUEST` ("aplicar_cura").
    - **Costo de antídoto:** Curar un Zombie Grande consume **2 dosis**; curar un Zombie Normal consume **1 dosis**.
    - Revierte al zombie nuevamente a `PersonaAgent` sano (`total_infectados -= 1`, `total_curados += 1`).
    - **Escolta** al humano curado guiándolo directamente hacia la salida de emergencia más cercana.
    - **Aspecto visual 3D:** Atuendo médico blanco, gorrito blanco con cruz roja y cruz médica roja 3D en el pecho.

## Levantamiento del Proyecto
```bash
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Controles
- **Clic izquierdo + Arrastrar / Flechas**: Orbitar cámara 3D.
- **Rueda del ratón**: Zoom.
- **`0` / `1`..`8`**: Ver todo el edificio o enfocar un piso específico.
- **`Espacio`**: Pausar / Reanudar.
- **`+` / `-`**: Velocidad de simulación (`0.5x` - `5.0x`).
- **`Q` / `W`**: Disminuir / Aumentar `N` personas y reiniciar.
- **`A` / `S`**: Disminuir / Aumentar `M` zombies y reiniciar.
- **`R`**: Reiniciar simulación actual.
- **`M`**: Silenciar / Activar audio.
