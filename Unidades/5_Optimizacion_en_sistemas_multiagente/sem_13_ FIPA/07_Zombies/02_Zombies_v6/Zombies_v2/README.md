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

## Caza Coordinada entre Zombies (`INFORM presa_detectada`)
- Cuando un zombie entra en persecución (`chasing = True`) envía un `INFORM` con contenido `"presa_detectada"` a todos los zombies en un **radio 3D de 12.0 m** (mismo piso y pisos adyacentes; altura de piso = 4.6 m). Cooldown de 4 s por zombie para no saturar el canal.
- El mensaje lleva la presa, su piso y posición, y una **asignación de salida por receptor**: las salidas se ordenan por cercanía a la presa (la primera es su ruta de escape más probable) y se reparten entre los receptores más cercanos a cada una.
- Los receptores (`ZombieReceiverBehaviour`) **abandonan la patrulla aleatoria** y van a emboscar su salida asignada. Si están en un piso adyacente, primero usan la escalera de emergencia más cercana para pasar al piso de la presa.
- En emboscada, el zombie espera junto a la salida mirando al pasillo y solo ataca si una persona se acerca a menos de 4 m. La emboscada termina a los 12 s o cuando la presa se salva o es infectada.
- Visualización: los mensajes `presa_detectada` se dibujan en **naranja**; los zombies **emboscando** se pintan naranja y los que **saltan desde una emboscada** en amarillo. El HUD muestra cuántos están emboscando, los avisos enviados y los infectados por emboscada.

## Correcciones
- **Atasco en puertas**: los zombies que perseguían a alguien dentro de un aula se quedaban congelados en la puerta (la puerta está justo fuera del área del aula). Ahora, al llegar a la puerta, la cruzan hacia el objetivo.
- **Superposición de zombies**: se agregó separación entre zombies para que no se apilen (por ejemplo, el recién convertido encima del que mordió).
- **Velocidad de simulación**: `+`/`-` ahora sí cambian la velocidad (antes se usaba una variable fija en 1.0).

## Pruebas
```bash
python test_horda.py
```
Ejecuta sin ventana: radio de 12 m y pisos adyacentes del INFORM, reparto de salidas, cambio de piso, modo horda OFF, fix de puertas y una simulación completa de 60 s.

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
- **`H`**: Activar / Desactivar el **modo horda** (caza coordinada). Se mantiene al reiniciar con `R`, para comparar resultados.
- **`R`**: Reiniciar simulación actual.
- **`M`**: Silenciar / Activar audio.
