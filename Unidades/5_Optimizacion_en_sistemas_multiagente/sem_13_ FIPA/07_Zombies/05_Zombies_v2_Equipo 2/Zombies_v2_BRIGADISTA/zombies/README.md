# Simulación Multi-Agente 3D: Invasión Zombie en la Universidad

Simulación 3D interactiva desarrollada en **Python + PyGame + NumPy** con arquitectura de agentes basada en comportamientos (`CyclicBehaviour`, `TickerBehaviour`, `ParallelBehaviour`) y mensajería FIPA-ACL (`INFORM`, `ALERT`, `CONFIRM`).

## Escenario Modelado
- **Edificio Universitario**: 8 pisos (`Piso 1` a `Piso 8`).
- **Distribución por piso**: 4 aulas (`Aula_1` a `Aula_4`), 1 pasillo central y 3 salidas de emergencia (`Salida_1`, `Salida_2`, `Salida_3`).
- **Agentes**:
  - `HostAgent`: Inicializa la plataforma y despliega `N` personas y `M` zombies.
  - `EdificioAgent`: Coordina reportes ACL y contabiliza cuántos se salvan y cuántos se infectan.
  - `PersonaAgent`: Evacúa desde las aulas/pasillos hacia las salidas de emergencia evitando zombies cercanos.
  - `ZombieAgent`: Patrulla salones (45%), pasillos (45%) y con baja probabilidad salidas de emergencia (10%), persigue personas e infecta al morder.

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
