# Spec inicial

Qué se decidió construir y por qué, antes de escribir código. La especificación completa es [specs/spec1.md](../../specs/spec1.md), escrita el 21 de septiembre de 2026 antes de la primera línea de `src/`; esto es su resumen razonado.

## El orden: dominio, verificación, arquitectura, spec y código

El proyecto arrancó de cero el 21 de septiembre de 2026 en la rama `novelasv2`, y lo primero que se escribió no fue código:

1. **El dominio**: [definitions.md](../definitions.md) (qué entidades tiene una novela: personajes, hechos, escenas, siembras, hilos) y [domain-knowledge.md](../domain-knowledge.md) (55 principios de oficio narrativo).
2. **Cómo se comprueba**: [validators.md](../validators.md), el catálogo de métodos de verificación con su etiqueta T/A/I/D/U.
3. **La arquitectura**: [architecture.md](../architecture.md), derivada de los dos anteriores.
4. **La spec**: spec1, con requisitos numerados que el código y los tests citan.

La razón del orden es que cada agente del sistema escribe entidades de la ontología, con criterios del oficio, y se comprueba con métodos del catálogo. Sin esos tres documentos, un agente no tiene ni qué producir ni cómo saber si lo hizo bien.

> **Por qué se empezó de cero.** El repositorio tuvo antes un primer harness (del 15 al 20 de septiembre, visible en el historial de git), con subagentes y hooks dentro de Claude Code, una web y Langfuse. La profesora pidió construir un proyecto nuevo sin borrar el anterior, así que el primero se conserva en la rama `main` y este vive en `novelasv2`, sin intención de fusionarlos. Se aprovechó para invertir el orden de trabajo: primero dominio, verificación y arquitectura; después código.

## Qué se decidió construir

Un **sistema con dos mitades**: un backend que genera la novela de forma autónoma y un frontend desde el que se arranca, se vigila y se lee. La v1 construye el backend entero y deja al frontend un contrato OpenAPI.

| Pieza | Decisión | Por qué |
| --- | --- | --- |
| Orquestación | **Código propio en Python**, no un agente | Todo lo que tiene una respuesta correcta única (qué fase toca, qué contexto entra, qué puerta se aplica) es código. El juicio queda para los agentes |
| Agentes | **Uno por fase** del proceso de escritura, cada uno con su skill | Cada fase tiene entrada, salida y criterio de terminación propios; ningún agente ve más contexto del que su fase necesita |
| Motor | **Claude Code por terminal**, sin herramientas y con la skill como prompt de sistema | Sin clave de proveedor que gestionar; las skills son ficheros versionados con el código |
| Memoria | **Story bible en SQLite**: el canon como grafo de hechos con su escena de origen | La continuidad pasa a ser una consulta, no una opinión |
| Verificación | **Puertas deterministas primero**, juicio después | Preguntarle a un modelo si hay una contradicción es caro y poco fiable cuando la respuesta está en una consulta |
| Ejecución | **API más worker** sobre una sola base, con la cola dentro de ella | El pipeline dura horas: tiene que sobrevivir a un reinicio de la API y poder reanudarse |

## La restricción que dio forma a todo

**100.000 tokens por llamada al modelo.** Obliga a que el contexto se ensamble por selección y no por volcado, y es la razón de que la unidad de trabajo sea el **capítulo**: más pequeño, el redactor no ve el arco; más grande, no cabe junto con su canon y los conflictos se detectan demasiado tarde.

## Qué se dejó fuera, y por qué

| Fuera de la v1 | Motivo |
| --- | --- |
| Revisor y pasadas globales | Dependen de la revalidación en cascada, que exige modelar dependencias entre hechos |
| Juicio de las puertas 1 y 5 | Su parte determinista sí entra, y es la que invalida trabajo posterior |
| Frontend | Tiene abierta la decisión de qué ve el autor |
| Multiusuario, varias obras a la vez | Contradicen las premisas de la arquitectura: un autor, una obra, máquina propia |

Lo que ha cambiado desde entonces está en el [registro de iteraciones](registro-iteraciones.md); lo que falta para la entrega, en el [plan de entrega](../../specs/storymaker-plan.md).
