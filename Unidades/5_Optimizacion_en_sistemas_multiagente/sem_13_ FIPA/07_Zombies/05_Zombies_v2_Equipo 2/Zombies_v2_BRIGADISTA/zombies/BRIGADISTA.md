# Caso: BrigadistaAgent en la Invasión Zombie

## 1. Enunciado del caso

Crear una nueva clase `BrigadistaAgent`:

- 1 por piso, desplegado por `HostAgent`.
- Mayor velocidad y campo de visión de 18.0 m.
- Emite mensajes `REQUEST "siganme"` a las personas que aún permanecen dentro de las 4 aulas de su piso.
- Las guía en formación hacia la salida de emergencia más segura.

Reglas aclaradas con el profesor:

1. Al **tocar** a una persona, esta adquiere la **misma velocidad** y sigue la **misma ruta** que el brigadista.
2. **Capacidad mínima:** el brigadista solo va a la salida con al menos **2 personas** (`MIN_GRUPO = 2`).
3. El brigadista **puede ser mordido**. Si lo muerden, **todas las personas que lo acompañan se infectan**.

Decisiones de diseño propias (para evitar bloqueos):

- Si en el piso ya no queda nadie más por recoger, el brigadista sale con lo que tenga (aunque sea 1 persona). Si exigiera 2 cuando solo queda 1, esperaría para siempre: sería un **deadlock**.
- Después de dejar a su grupo en la salida, **vuelve a recolectar** si quedan personas en las aulas. Si no queda nadie, sale él también ("piso despejado").

---

## 2. Archivos modificados

| Archivo | Cambio |
|---|---|
| `agents/brigadista_agent.py` | **Nuevo.** Clase `BrigadistaAgent` y sus 3 behaviours |
| `agents/persona_agent.py` | Modos `LIBRE` / `LLAMADA` / `SIGUIENDO`; responde al REQUEST; sigue la ruta del líder |
| `agents/zombie_agent.py` | También persigue y muerde brigadistas |
| `agents/host_agent.py` | Despliega `Brigadista_P1` … `Brigadista_P8` |
| `agents/universidad_agent.py` | El Edificio registra en el log los reportes de los brigadistas |
| `agents/acl.py` | Performativa `AGREE` y contadores `guiados_salvados` y `brigadistas_caidos` |
| `graphics/engine3d.py` | Dibuja al brigadista (naranja chaleco) |
| `graphics/hud.py` | Muestra "Brigadistas: X (caídos Y), guiados salvados: Z" |

En el código, cada cambio está marcado con `[MOD]` o `[NUEVO]`.

### Qué se reutilizó

- `TickerBehaviour`, `CyclicBehaviour` y `ParallelBehaviour` (el mismo esquema que persona y zombie).
- `building.get_room_containing()` para saber si una persona sigue dentro de un aula.
- La **fórmula de la salida más segura** de `PersonaAgent`: distancia + penalización por zombies cerca de la salida.
- El **vector de evasión** de zombies de la persona, usado también por el brigadista.
- La lógica de **rutas por puertas** del zombie (si está en otra zona, primero va a la puerta del aula).
- `PersonaAgent.infectar()`, que ya crea el zombie convertido. La cascada simplemente la llama para cada seguidor.
- `_queue_articulated_character()` para dibujar al brigadista con otro color.

---

## 3. Lógica del brigadista

### Atributos

| Atributo | Valor | Por qué |
|---|---|---|
| `speed` | 5.0 | Más rápido que una persona corriendo (3.9 – 4.6) |
| `vision_radius` | 18.0 | Más que un zombie (14.5); cubre casi todo su piso desde el pasillo |
| `grupo` | lista de nombres | Seguidores **en orden de fila** |
| `llamados` | conjunto | Personas que ya recibieron el REQUEST (para no repetirlo) |
| `ruta` | `deque` de posiciones | Migas de pan (*breadcrumbs*): la ruta exacta que pisan los seguidores |

### Behaviours (dentro de un `ParallelBehaviour`)

| Behaviour | Tipo | Función |
|---|---|---|
| `BrigadistaLlamadoTicker` | Ticker, cada 2 s | Envía `REQUEST "siganme"` a las personas sanas de su piso que estén **dentro de un aula** y **a 18 m o menos** |
| `BrigadistaReceiverBehaviour` | Cyclic | Recibe el `AGREE` de las personas que aceptan |
| `BrigadistaMoverBehaviour` | Cyclic | Limpia el grupo, recoge por contacto, cambia de estado, elige el objetivo, se mueve esquivando zombies y guarda su ruta |

### Máquina de estados

```
RECOLECTANDO ──(grupo ≥ 2, o grupo ≥ 1 y no quedan pendientes)──▶ GUIANDO
RECOLECTANDO ──(grupo vacío y no quedan pendientes)──────────────▶ RETIRANDO
GUIANDO ──(llega a la salida)──▶ EN_SALIDA  (se detiene y deja pasar al grupo)
EN_SALIDA ──(todo el grupo salió)──▶ RECOLECTANDO (si quedan personas) │ RETIRANDO
RETIRANDO ──(llega a una salida)──▶ SALVADO ("piso despejado", se elimina)
cualquiera ──(mordida)──▶ INFECTADO (se convierte en zombie + su grupo se infecta)
```

### Contacto y formación ("misma velocidad, misma ruta")

1. Cuando una persona llamada (o que está en un aula) queda **a 1.5 m o menos** del brigadista, este la **une** al grupo con `unir()`.
2. Le envía `INFORM "unido"` con su **slot** (puesto en la fila) y la persona pasa a modo `SIGUIENDO` (se pinta de amarillo).
3. Cada 0.3 m que avanza, el brigadista guarda un punto en `ruta`.
4. El seguidor con slot *k* camina hacia el punto de la ruta que está **4·(k+1) puntos atrás**, es decir, a 1.2 m por cada puesto. Así forman una **fila india** que pisa **exactamente** por donde pasó el brigadista, incluidas las puertas de las aulas.
5. El seguidor se mueve a la **velocidad del brigadista** (`lider.speed`) y **no huye por su cuenta**: delega esa decisión en el líder.
6. Cuando el brigadista llega a la salida (`EN_SALIDA`), los seguidores van directo a la salida y se salvan con el `salvar()` de siempre.

### Salida más segura

Para cada salida del piso:

```
costo = distancia(brigadista, salida) + Σ (6.0 − d_zombie_salida) · 8   para cada zombie a menos de 6 m de la salida
```

Se elige la de menor costo. Es la misma fórmula de la persona, pero con un radio de riesgo mayor (6 m en vez de 4.5) porque el brigadista ve más lejos. Se **recalcula en cada paso** mientras guía, así que si aparece un zombie en la salida elegida, cambia de salida.

### Mordida en cascada

`BrigadistaAgent.infectar()`:

1. Envía `ALERT "brigadista_mordido"` al Edificio con el tamaño del grupo.
2. Llama a `persona.infectar()` para **cada seguidor**, y cada uno se convierte en zombie.
3. El brigadista también se convierte en zombie y se elimina.

El zombie no necesita saber si mordió a una persona o a un brigadista: llama a `target.infectar()` y cada clase sabe qué hacer. Es **polimorfismo**.

---

## 4. Cambios en la persona

Nuevo atributo `modo`:

| Modo | Cómo entra | Qué hace |
|---|---|---|
| `LIBRE` | Inicial | Comportamiento original: sale del aula y va a la mejor salida, huyendo de los zombies |
| `LLAMADA` | Recibe `REQUEST "siganme"` y responde `AGREE` | Camina hacia el brigadista (saliendo por la puerta si están en zonas distintas) y sigue esquivando zombies |
| `SIGUIENDO` | Contacto con el brigadista (recibe `INFORM "unido"`) | Va a su punto de la fila con la velocidad del líder. Ignora el pánico (`peligro_zombie`) |

Si el líder desaparece (mordido o fuera del edificio), la persona vuelve a `LIBRE` y evacúa sola.

---

## 5. Protocolo de mensajes nuevo

| De → Para | Performativa | Contenido | Datos |
|---|---|---|---|
| Brigadista → Persona | **REQUEST** | `"siganme"` | `{lider}` |
| Persona → Brigadista | **AGREE** | `"voy"` | — |
| Brigadista → Persona | INFORM | `"unido"` | `{lider, slot}` |
| Brigadista → Edificio | INFORM | `"grupo_en_salida"` | `{salida, personas}` |
| Brigadista → Edificio | ALERT | `"brigadista_mordido"` | `{atacante, grupo, piso}` |
| Brigadista → Edificio | INFORM | `"brigadista_fuera"` | `{salida}` |

`REQUEST` → `AGREE` es el protocolo **FIPA-Request**: un agente pide que otro **haga una acción** (seguirlo), y el otro acepta el compromiso.

---

## 6. Conceptos del curso aplicados

| Concepto | Dónde se ve |
|---|---|
| **Organización y roles** (semana 12, la O de VOWELS) | Aparece un rol nuevo, el líder, con la relación líder → seguidores. Antes todos los agentes eran iguales |
| **Delegación** (principio de agente, semana 12) | La persona en `SIGUIENDO` cede su decisión de ruta y velocidad al brigadista |
| **Actos de habla / FIPA-ACL** | `REQUEST` (pedir una acción) es distinto de `INFORM` (informar un hecho) y de `ALERT`; `AGREE` es el compromiso |
| **Protocolo de interacción** | FIPA-Request: REQUEST → AGREE → (acción) → INFORM |
| **Agente basado en utilidad** (semana 11) | La salida "más segura" minimiza un costo de distancia + riesgo |
| **Agente híbrido** (reactivo + deliberativo) | Reacciona (esquiva zombies, recoge por contacto) y delibera (máquina de estados, capacidad mínima, elección de salida) |
| **Situado / pro-activo / social** | Percibe su piso a 18 m, busca personas por iniciativa propia y se comunica con personas y con el Edificio |
| **Descentralización** | 8 brigadistas independientes, uno por piso; no hay un coordinador global de rescate |
| **Comportamiento colectivo** | La fila india es una formación **dirigida por un líder**; se contrasta con el enjambre de peces, donde la formación **emerge** |
| **Deadlock y su prevención** | La regla "sale con lo que tenga si no quedan pendientes" evita esperar para siempre con 1 persona |
| **Polimorfismo** | El zombie llama a `infectar()` sin saber si es persona o brigadista |

---

## 7. Resultados de prueba

Simulación sin pantalla, 90 s, N=32 personas, M=12 zombies, 5 semillas:

| Semilla | Salvados | Guiados por brigadista | Infectados | Brigadistas caídos |
|---:|---:|---:|---:|---:|
| 1 | 23 | 14 | 6 | 4 |
| 2 | 22 | 12 | 8 | 4 |
| 3 | 24 | 10 | 6 | 5 |
| 4 | 23 | 12 | 4 | 3 |
| 5 | 16 | 8 | 13 | 5 |

- Entre **8 y 14 personas por corrida** se salvan gracias a un brigadista.
- Hay **más infectados que en el original** (que tenía 0 a 3). No es porque el brigadista empeore las cosas: en el original casi no había infecciones porque **zombie y persona se bloqueaban en la puerta del aula** (deadlock). El brigadista entra y saca a la gente de las aulas, así que hay más contacto real con zombies, y cuando muerden a un brigadista se activa la **cascada**.
- Todavía quedan 2 a 5 personas atascadas por ese bloqueo zombie-puerta. Es el siguiente paso a corregir.

---

## 8. Pendiente: deadlock zombie-puerta

Cuando el zombie está en el pasillo y la persona dentro del aula, el zombie va a la **puerta** del aula y se queda ahí parado (su objetivo es la puerta). La persona quiere salir por esa puerta pero huye del zombie. Quedan a unos 1.5 m, justo fuera del rango de mordida (1.15 m), y ninguno avanza.

Solución planeada: si el zombie ya está a menos de 1 m de la puerta, que vaya **directo** a la persona. El brigadista ya trae esta corrección en `navegar_hacia()`; por eso él no se queda atascado en las puertas.
