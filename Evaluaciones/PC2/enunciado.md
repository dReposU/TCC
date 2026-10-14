1. 
Un hospital debe asignar a 3 médicos (M1,M2,M3) a 3 turnos diferentes (Mañana, Tarde, Noche).

Cada médico debe tener exactamente un turno, y ningún turno puede estar sin médico. Debido a restricciones médicas y de agenda:

M1 no puede trabajar en la Noche.
M2 no puede trabajar en la Mañana.
M3 debe trabajar después de M1 pero antes de M2 (en un turno cronológicamente posterior).
Modele formalmente este problema como un Problema de Satisfacción de Restricciones (CSP). Defina claramente:
(1 punto) El conjunto de Variables (X).
(1 punto) El dominio de cada variable (D), indicando cómo mapeará los turnos a valores numéricos para representar el tiempo.
(1 punto) El conjunto de restricciones formales (C).
(1 punto) ¿La solución es única? o ¿existe más de una?.
(1 punto) Imprima el tiempo de ejecución del modelo con la función walltime del solver.

2. 

Dado un CSP con cuatro variables H, I, J, K, todas con el dominio inicial D={1,2,3,4,5}.

Se tienen las siguientes tres restricciones que cubren a las cuatro variables:

C1: H > 2
C2: I = H + 2
C3: J + K < I
(1 punto) ¿cual es la aridad de las restricciones C1, C2 y C3?
(2 puntos) Dibuje el grafo de variables (nodos = variables, aristas/hiper-aristas = restricciones indicando qué variables conectan).
(2 puntos) Aplique la propagación lógica (filtrado) paso a paso de forma manual. Muestre detalladamente cómo se reducen los dominios en cada paso analizando C1, luego C2, y finalmente C3. Indique explícitamente cuáles son los dominios finales de H, I, J, K.

3.

Usted dirige una obra con un equipo máximo de 5 obreros disponibles en todo momento (Capacidad). Tiene 3 tareas con los siguientes requerimientos:

Tarea 1: Duración = 2 días, Obreros necesarios = 3
Tarea 2: Duración = 3 días, Obreros necesarios = 2
Tarea 3: Duración = 1 día, Obreros necesarios = 4
Todas las tareas deben completarse en un horizonte temporal de 10 días (del día 0 al 10).
(1 punto) Explique cómo funciona internamente la restricción global cumulative.
(1 punto) ¿Qué ventaja tiene evaluar el "perfil de recursos" globalmente en el tiempo en comparación a intentar modelar esto de forma ingenua verificando que las tareas no se superpongan en el tiempo por pares?
Asumiendo que las duraciones y demandas son constantes, escriba el código en OR-Tools para:
(1 punto) Declarar las variables de inicio (start), fin (end) e intervalo (interval) para cada una de las 3 tareas.
(2 puntos) Agregar la restricción global AddCumulative para asegurar que nunca se exceda el límite de los 5 obreros.

4.

En un sistema de asignación, se tienen las variables PA (Proyecto A) y PB (Proyecto B), ambas con dominio de días {1,2,3,4,5}. Existen tres reglas condicionales estrictas:

Si el Proyecto A se asigna al día 3, entonces el Proyecto B debe asignarse al día 4.
Si el Proyecto A se asigna al día 4, entonces el Proyecto B debe asignarse al día 5.
Si el Proyecto B se asigna al día 1, entonces el Proyecto A debe asignarse al día 5.
Defina las variables booleanas reificadas que representen los "antecedentes" de estas condiciones (la parte del "Si...").
(1 punto) Escriba las equivalencias formales para esas booleanas y cómo quedarían las implicaciones lógicas hacia las consecuencias.
(2 puntos) Muestre la reificación bidireccional de los antecedentes y las implicaciones hacia los consecuentes.
(2 puntos) Implemente estas tres reglas condicionales en OR-Tools utilizando variables booleanas explícitas y el método .OnlyEnforceIf().