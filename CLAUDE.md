# Claude Code en storyMaker

storyMaker genera novelas de terror espacial con un harness de agentes: un orquestador en Python que encadena agentes de Claude Code, guarda el canon en una story bible SQLite y no acepta un capítulo hasta que pasa sus puertas de control. Las reglas del proyecto están en `AGENTS.md`, que se importa aquí; este fichero añade solo lo que cambia cuando quien trabaja es Claude Code.

@AGENTS.md

## Por dónde empezar

| Si vas a… | Lee primero |
| --- | --- |
| Tocar `src/backend/` | [specs/spec1.md](specs/spec1.md) y [specs/spec2.md](specs/spec2.md), que la refina. Cada requisito se cita por su código (`RF-…`, `RF2-…`) |
| Saber qué falta para la entrega | [specs/storymaker-plan.md](specs/storymaker-plan.md) |
| Decidir cómo se comprueba algo | [docs/validators.md](docs/validators.md): etiqueta T/A/I/D/U y punto ciego para cada propiedad |
| Documentar el proceso | [docs/proceso/](docs/proceso/README.md) |

## Comandos del proyecto

- `/verificar`: tests, ruff y pyright del backend. Los tres salen limpios antes de cada commit.
- `/demo-falsa`: el pipeline entero con el puerto falso sobre una base temporal. Cuesta cero.
- `/validar-cambio <ref>`: lanza el subagente `validador-de-codigo` sobre un commit o un rango.
- `/sincronizar-memoria`: copia la memoria de Claude Code a `.claude/memoria/` para que quede en el repo.

Todo comando del backend se ejecuta desde `src/backend` con `.venv\Scripts\python.exe`: el entorno es Windows y lanzados desde otro sitio no encuentran los módulos. El detalle está en [src/backend/README.md](src/backend/README.md).

## Lo que cuesta dinero o toca datos del autor

- **Claude Code real cuesta dinero** (unos 0,50 $ por llamada de agente). Pide aprobación antes de cualquier ejecución con `NOVELAS_PUERTO=terminal` o de `pytest -m agente`. Para todo lo demás, el puerto falso.
- **`src/backend/novela.db` es la base del autor**, y a menudo tiene su propio worker vivo encima. Trabaja sobre una base temporal o una copia. Para detener un worker que lanzaste tú, usa el pid que capturaste al lanzarlo: en Windows cada worker son dos procesos con la misma línea de comandos, y filtrar por patrón para también el del autor.

## Las skills de `.claude/skills/`

Casi todas son el **prompt de sistema de un agente en ejecución**, no instrucciones para ti: el puerto lee la `SKILL.md` y se la entrega a Claude Code como sistema. Cambiar una es cambiar el comportamiento de ese agente, así que entra con su spec y sus tests en el mismo commit (RF-SKILL-01). La excepción es `verificacion`, que es de desarrollo: úsala para construir o revisar un plan de verificación.

## Cerrar un paso

1. `/verificar` en verde.
2. La spec y el plan de verificación actualizados en el mismo commit que el código.
3. `/validar-cambio` sobre el commit. Un veredicto RECHAZADO se corrige antes de seguir.
4. Si el paso cambió algo por un fallo, una eval o un contraejemplo, añade la entrada al [registro de iteraciones](docs/proceso/registro-iteraciones.md).

Los mensajes de commit van en castellano sin tildes y en infinitivo o con el nombre de la fase (`Fase 3 de spec2: un solo escritor, de verdad`).
