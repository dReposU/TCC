# Simulación 3D de Torre de Control Multi-Agente (JADE → Python + PyGame)

Adaptación interactiva y visual en **3D** de un sistema multi-agente originalmente desarrollado en **Java con JADE** (`HostAgent.java`, `TorreAgent.java` y `AvionAgent.java`).

## Estructura del Proyecto

```text
simulacion_torre_control_3d/
├── main.py                     # Bucle principal PyGame 3D y control de cámara/eventos
├── requirements.txt            # Dependencias (pygame, numpy)
├── README.md                   # Documentación del proyecto
├── agents/
│   ├── acl.py                  # Protocolo FIPA-ACL (INFORM, PROPOSE, ACCEPT/REJECT_PROPOSAL) y DFService
│   ├── behaviours.py           # Comportamientos JADE (CyclicBehaviour, TickerBehaviour, ParallelBehaviour)
│   ├── torre_agent.py          # TorreAgent: exclusión mutua de pista (pista_ocupada)
│   ├── avion_agent.py          # AvionAgent: patrón de espera 3D, solicitudes y aterrizaje
│   └── host_agent.py           # HostAgent: despliegue de Torre y 10 agentes Avion
├── graphics/
│   ├── engine3d.py             # Motor 3D en perspectiva (modelos .obj, iluminación, ondas ACL 3D)
│   └── hud.py                  # HUD con consola de mensajes ACL en tiempo real
└── assets/
    ├── models/                 # Mallas 3D (.obj): airplane.obj, control_tower.obj, hangar.obj
    ├── textures/               # Sprites y texturas (.png): radar_icon.png, runway_markings.png
    └── sounds/                 # Efectos de audio (.wav): radio_ping, landing_accept, landing_reject, touchdown
```

## Instalación y Ejecución

1. Crear o activar un entorno virtual de Python (recomendado Python 3.9+):
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```
2. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Ejecutar la simulación 3D:
   ```bash
   python main.py
   ```

## Controles Interactivos

- **Clic izquierdo + Arrastrar / Flechas**: Orbitar la cámara 3D alrededor del aeropuerto.
- **Rueda del ratón**: Acercar / Alejar zoom.
- **Teclas `1` - `4`**: Cambiar entre vistas de cámara (Órbita Libre, Torre de Control, Seguir Avión Aterrizando, Panorámica Aérea).
- **`Espacio`**: Pausar / Reanudar la simulación.
- **`+` / `-`**: Aumentar o reducir la velocidad de simulación (`0.5x` a `5.0x`).
- **`N`**: Desplegar un nuevo agente avión en tiempo real.
- **`R`**: Reiniciar toda la plataforma multi-agente.
- **`M`**: Silenciar / Activar efectos de sonido.
