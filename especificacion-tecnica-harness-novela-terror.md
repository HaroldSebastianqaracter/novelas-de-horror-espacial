# Especificación Técnica — Harness Generador de Novelas de Terror

**Versión:** 1.8 — historial de cambios en `git log` sobre este archivo.
**Documento base:** `especificacion-funcional-harness-novela-terror.md` v1.8 — todo lo que sigue implementa esos requisitos (RF-XX) sin redefinir su comportamiento.
**Lector previsto:** el agente de código que implementa el harness. Toda decisión no cubierta aquí y no derivable de la especificación funcional debe tratarse como pregunta abierta, no como espacio para asumir.

## 1. Decisiones de arquitectura declaradas

Decisiones tomadas para poder avanzar, con su razón — si alguna deja de aplicar, hay que revisar en cascada lo que depende de ella.

| Decisión | Razón |
|---|---|
| Orquestación: **Claude Code** (sesión principal + subagentes) | Indicación de la dirección del proyecto. Cada agente del pipeline es un subagente con contexto aislado y allowlist de herramientas, así que INV-01, INV-02 e INV-05 pasan de ser reglas de prompt a configuración declarativa (§13.1). |
| Scripts deterministas: **Python 3.11+ en el paquete `app/`, sin llamadas a modelo y sin servidor** | Todo lo que debe ser reproducible y testeable sin LLM — validación de esquemas, filtrado de continuidad, aplicación de deltas, manifiesto, registro, `resolver`, `ensamblar`, `ui` y los scripts de los hooks — vive en Python y lo invocan las skills (por línea de comandos), los agentes (solo su validador, §13.1) y Claude Code (por hooks). No hay FastAPI ni ningún proceso escuchando, salvo el formulario local de §15 mientras el usuario lo usa. Claude Code decide; los scripts hacen cumplir. El paquete **no** se llama `harness/`: "harness" designa al conjunto (agentes, skills, hooks y scripts), y usar ese nombre para una de sus partes induce a error. |
| **Cumplimiento por hooks, no por prompt** (RF-08.2) | Cada invariante verificable ante un evento tiene un hook en §13.3. Los ejecuta Claude Code, no el agente: el agente ni sabe que existen. Lo que no cubre ni un hook ni una allowlist se declara límite conocido en §13.6, con nombre. |
| **Autovalidación dentro del bucle del agente** (RF-08.4) | Cada agente ejecuta su propio validador antes de terminar y corrige solo. Antes, una salida inválida costaba una invocación entera del orquestador para reintentar, y su error atravesaba el contexto de la sesión principal. El precio es dar `Bash` a los tres agentes, que H-11 acota a un único comando por rol. |
| **Registro de ejecución** (RF-08.5) | Una tanda deja en `07_registro/` los eventos, los prompts, los retornos y los descartados. Sin él, depurar una tanda fallida obliga a releer la conversación del orquestador, que no es reproducible ni auditable. |
| Acceso a modelos: **Claude Code enrutado a OpenRouter** | `ANTHROPIC_BASE_URL` apunta a OpenRouter con una credencial de OpenRouter; la suscripción de claude.ai no interviene y no hay adapter propio (§3). Modelo por rol mediante alias de subagente. |
| **Modelos distintos por rol** | Escritor y QA usan el modelo capaz; el extractor, el económico. El escritor por calidad de prosa. QA porque cruza ~34.000 tokens de prosa contra el log completo de hechos: es razonamiento sobre contexto largo, justo donde los modelos económicos flojean, y un falso negativo suyo es el peor fallo del sistema — una contradicción no detectada sigue viva y el escritor construye encima. El extractor sí es una tarea mecánica (un capítulo → JSON) cuyo error lo atrapa la validación de esquema. Detalle de costes en §11.7. |
| **Esquemas formales con Pydantic** | Valida cada artefacto de estado antes de persistirlo; permite rechazar y reintentar cuando el LLM produce JSON inválido (EX-01). |
| **Checkpointing/reanudación** | Los artefactos ya se persisten en disco por capítulo (§5); el harness debe poder detectar dónde quedó una tanda interrumpida y continuar sin repetir capítulos cerrados. |

## 2. Arquitectura de módulos

Todas las rutas de este documento son relativas a `creador-novelas/`, la carpeta del repositorio donde vive el harness. Las specs y los diagramas quedan en la raíz del repositorio y no se mueven.

```
app/
├── config.py                 # carga y valida la carpeta config/ (§11.1)
├── schemas/
│   ├── personajes.py          # Personaje, FichaPersonajes
│   ├── continuidad.py         # HechoContinuidad, LogContinuidad
│   ├── outline.py             # EntradaOutline, Outline
│   ├── qa.py                  # Hallazgo, ReporteQA
│   ├── deltas.py               # DeltaExtraccion
│   └── mundo.py                # Mundo (RF-04.2; locaciones → registro de sujetos)
│   (no hay capa llm/: el acceso a modelos es el de Claude Code enrutado a OpenRouter — §3;
│    los agentes son subagentes en .claude/agents/ y las fases skills en .claude/skills/ — §13)
├── agents/
│   ├── escritor.py             # RF-05.1, RF-05.2
│   ├── extractor.py            # RF-06.1
│   └── qa.py                   # RF-07.1, RF-07.2, RF-07.3
├── state/
│   ├── repository.py           # lectura/escritura con validación (EX-01)
│   ├── continuidad.py          # append-only, filtrado por relevancia (RF-06.3, RF-05.1, INV-03)
│   ├── personajes.py           # aplicar deltas, registro de sujetos (RF-06.2, RF-06.1)
│   └── resumen_rodante.py      # ventana deslizante (RF-06.4)
├── orchestrator/
│   ├── loop.py                 # loop principal fases 5-7
│   └── checkpoint.py           # detecta último capítulo cerrado, permite reanudar
├── cli.py                      # capa externa y verbos internos del loop (§8.2)
├── ui.py                       # frontend: formulario y panel de fases (§15)
└── __main__.py                 # python -m app
```

Regla de dependencia que el agente implementador debe respetar: `agents/escritor.py` **no importa** `state.repository.leer_manuscrito` bajo ninguna firma — es la forma de hacer cumplir INV-01 (el escritor nunca lee capítulos cerrados) a nivel de código, no solo de prompt.

Fuera del paquete `app/` viven los archivos que Claude Code lee directamente:

```
.claude/
├── agents/                   # escritor.md · extractor.md · qa.md — §13.1
├── skills/                   # una carpeta por fase + skills de dominio por agente — §13.2, §11.8
└── settings.json             # hooks (§13.3) y bloque env sin credencial (§3.1)
scripts/hooks/                # un script por evento; deciden por agente y ruta e invocan `app/` — §13.3
CLAUDE.md                     # reglas ambientales, orden de fases, mapa de carpetas — §13.5
07_registro/                  # un directorio por tanda: eventos, prompts, retornos, descartados — §5.1
08_entrega/                   # salida derivada de `ensamblar`: la novela concatenada — §8.2
```

`app/` nunca importa nada de `.claude/` ni de `scripts/`; la dependencia va en un solo sentido: los scripts de hooks, el CLI y los validadores que ejecutan los agentes importan `app/`.

## 3. Acceso a modelos — Claude Code enrutado a OpenRouter

No hay capa `llm/` en Python. Los agentes son subagentes de Claude Code (§13.1) y usan la capa de modelo de Claude Code. Lo que se configura es **a dónde** manda Claude Code sus peticiones y **qué modelo** responde a cada alias.

### 3.1 Enrutamiento

Claude Code habla el formato Anthropic Messages (`/v1/messages`) con el host de `ANTHROPIC_BASE_URL`. OpenRouter expone ese formato directamente (lo llama "Anthropic Skin"), así que no hace falta proxy ni traductor:

```bash
export ANTHROPIC_BASE_URL="https://openrouter.ai/api"
export ANTHROPIC_AUTH_TOKEN="TU_CLAVE_OPENROUTER_AQUI"
export ANTHROPIC_API_KEY=""     # vacío a propósito: que ninguna clave de Anthropic pise al token
```

Con la credencial activa, la suscripción de claude.ai **no se usa**: cada token se factura a la cuenta de OpenRouter. Es exactamente el efecto buscado — Claude Code como orquestador, OpenRouter como proveedor.

Las mismas variables van en el bloque `env` de `.claude/settings.json` del proyecto, **salvo la credencial**, que nunca se versiona: vive en el entorno de la máquina.

### 3.2 Modelo por rol

Cada subagente declara un alias en su frontmatter (`model: opus` | `sonnet` | `haiku`). Los alias se resuelven a IDs de OpenRouter con variables de entorno:

| Rol | Frontmatter | Variable que lo resuelve | Tipo de modelo |
|---|---|---|---|
| Escritor | `model: opus` | `ANTHROPIC_DEFAULT_OPUS_MODEL` | capaz |
| QA | `model: opus` | la misma | capaz (§1, §11.7) |
| Extractor | `model: haiku` | `ANTHROPIC_DEFAULT_HAIKU_MODEL` | económico |
| Sesión principal (orquestador) | — | `ANTHROPIC_DEFAULT_SONNET_MODEL` | intermedio: decide, no escribe prosa |

Los IDs concretos se eligen en el momento de la corrida según el catálogo de OpenRouter, se documentan en `config/proveedores.json` (§11.4) y quedan registrados en el manifiesto (§5) para saber con qué se generó cada capítulo. El formato de ID es `anthropic/claude-<nombre>`; el prefijo `~` denota alias de OpenRouter y el sufijo `[1m]` solicita ventana de 1M tokens.

`CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` hace que el selector `/model` liste lo que la clave de OpenRouter puede usar; sirve para elegir IDs sin salir de Claude Code.

### 3.3 Modelos que no son Claude

OpenRouter advierte que Claude Code está optimizado para modelos Anthropic y "puede no funcionar correctamente con otros proveedores"; Anthropic declara ese uso como no soportado. Regla del proyecto:

- **Escritor y QA: siempre Claude vía OpenRouter.** Son los roles donde un fallo silencioso cuesta caro y donde importan las capacidades que otros modelos no exponen igual (thinking, tool use nativo, caché).
- **Extractor: se permite probar un modelo no-Claude más barato.** Su tarea es mecánica y su salida la valida Pydantic (EX-01), así que un fallo es visible, no silencioso. Si aparecen errores `400` por campos que el modelo no acepta, `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1` desactiva las capacidades pre-release que Claude Code envía; si persisten, se vuelve a Claude. Es una optimización a evaluar en la corrida de validación de §9, no un punto de partida.

### 3.4 Reintentos

Claude Code ya reintenta por su cuenta rate limits y errores de red del proveedor. Lo que queda del lado del harness es lo que Claude Code no puede saber: un delta que no valida contra el esquema se **reintenta reenviando el error de validación al subagente extractor**, hasta `reintentos.max_intentos` (§11.4), y luego dispara EX-01. La capa gratuita de OpenRouter tiene límites agresivos; `max_llamadas_por_tanda` (RF-CFG-06) es la protección del lado del harness para que una tanda mal calibrada no agote la cuota.

### 3.5 Conteo de tokens para RF-05.1

El criterio de aceptación de RF-05.1 exige no exceder `max_tokens_contexto_escritor`. El helper Python de ensamblado usa una estimación conservadora (`tiktoken` +15% de margen), documentada como aproximación y no como conteo exacto, para no dar falsa precisión.

## 4. Esquemas de datos (Pydantic)

Son la **única** fuente de esquemas del proyecto, como contrato validable. (El documento `harness-novela-terror.md` que citaban versiones anteriores nunca existió en el repositorio.)

```python
# schemas/personajes.py
class Personaje(BaseModel):
    estado_fisico: str
    estado_psicologico: str
    secretos_que_conoce: list[str] = []
    ultima_aparicion: int

class FichaPersonajes(RootModel[dict[str, Personaje]]): ...

# schemas/continuidad.py
class HechoContinuidad(BaseModel):
    sujeto: str                  # clave de personajes.json, locación de mundo.json, o "mundo"
    categoria: Literal["personaje", "locacion", "mundo"]
    sujeto_validado: bool = True # False si `sujeto` no estaba en el registro (RF-06.1)
    hecho: str                   # la formulación en prosa — es lo que lee el escritor
    cap_origen: int
    superado_por: int | None = None   # RF-07.6; nulo mientras el hecho siga vigente

class LogContinuidad(RootModel[list[HechoContinuidad]]): ...

# schemas/outline.py
class EntradaOutline(BaseModel):
    num: int
    titulo: str = Field(min_length=1)   # RF-03.1 — generado en fase 3, no por el escritor
    objetivo_narrativo: str
    personajes: list[str]
    locacion: str
    informacion_nueva: str
    tension: int = Field(ge=1, le=5)

# schemas/deltas.py
class DeltaExtraccion(BaseModel):
    personajes: dict[str, Personaje]   # solo los que cambiaron; claves del registro (RF-06.1)
    hechos_nuevos: list[HechoContinuidad]
    resumen_corto: str                  # 3-5 líneas

# schemas/qa.py
class Hallazgo(BaseModel):
    tipo: Literal["contradiccion", "repeticion"]
    descripcion: str
    cap_origen: int | None = None       # obligatorio si tipo == "contradiccion"

class ReporteQA(BaseModel):
    cap_corte: int
    hallazgos: list[Hallazgo]
    tiene_contradicciones: bool
```

`state/repository.py` valida contra estos modelos **antes** de escribir a disco. Una validación fallida dispara `EstadoInvalidoError` (EX-01) y detiene el loop sin persistir el artefacto corrupto.

```python
# schemas/mundo.py
class Mundo(BaseModel):
    reglas: list[str]                 # reglas del universo que condicionan la trama (RF-04.2)
    objetos: list[str]                # objetos relevantes
    linea_de_tiempo: list[str]        # hitos previos al capítulo 1
    locaciones: dict[str, str]        # clave canónica → descripción; las claves alimentan
                                      # el registro de sujetos (RF-06.1) y el filtro (RF-05.1)
```

`Mundo` no se inyecta al escritor (§11.7): lo que debe condicionar la escritura vive como hechos `categoria = "mundo"` en `continuidad.json`. Sus `locaciones` son la única parte que el sistema consume.

## 5. Artefacto técnico adicional: manifiesto de ejecución

No forma parte de la especificación funcional (es puramente de soporte técnico para checkpointing). Vive en `04_estado/manifest.json`:

```json
{
  "ultimo_capitulo_cerrado": 12,
  "ultimo_qa_ejecutado": 8,
  "total_capitulos_esperado": 40,
  "estado": "en_progreso",  // en_progreso | pausado_por_qa | completo — no hay "abortado", ver abajo
  "reporte_qa_pendiente": null,          // nombre del reporte sin resolver, o null (RF-07.4)
  "intentos_por_capitulo": { "7": 2 },   // solo capítulos que necesitaron reintento (EX-07/EX-08)
  "prompts_hash": { "escritor": "…", "extractor": "…", "qa": "…" },   // §11.5
  "reextraccion_pendiente": [],          // capítulos declarados corregidos y aún no reextraídos (RF-07.6, §8.2)
  "capitulo_activo": null,               // capítulo que el extractor puede leer durante una reextracción; null = ultimo_capitulo_cerrado + 1 (H-05)
  "tanda_actual": "tanda_2026-09-16T12-40-03",  // carpeta de §5.1 donde se registra la tanda en curso o la última
  "ultimo_error": null                   // texto del último fallo que detuvo la tanda; lo muestra status
}
```

`reporte_qa_pendiente` es lo que hace detectable una edición manual del manifiesto: `checkpoint.py` se niega a reanudar si `estado == "en_progreso"` pero este campo no es nulo, porque esa combinación solo puede producirla alguien que cambió el estado a mano sin pasar por `resolver` (§8.2). El único código que lo pone en nulo es `resolver`, tras ejecutar RF-07.6.

`orchestrator/checkpoint.py` lee este archivo al iniciar; si `estado == "pausado_por_qa"`, el harness no reanuda automáticamente (implementa RF-07.4) hasta que el usuario marque el reporte correspondiente como resuelto.

`total_capitulos_esperado` guarda el valor con el que se generó la escaleta. Al reanudar se compara contra `config.total_capitulos`; si difieren y `ultimo_capitulo_cerrado > 0`, se dispara EX-06.

El manifiesto **no** registra nada sobre la tanda en curso (ni el tope ni cuántos capítulos lleva). El conteo de `capitulos_por_tanda` vive solo en el cursor transitorio durante la ejecución: es un límite de esta corrida, no un hecho de la novela. Persistirlo daría a entender que la partición en tandas es parte del estado de la obra, y por INV-06 no lo es.

Lo que sí existe es un **cursor transitorio**, `.tanda/cursor.json`, fuera de `04_estado/`, ignorado por git y borrado cuando la tanda termina. Lo escriben únicamente los verbos `tanda` del CLI (§8.2) y guarda el tope y el conteo de la tanda en curso. No es un artefacto de estado: si aparece al abrir una sesión, es que la anterior murió a mitad, y `tanda iniciar` lo descarta y recalcula desde el manifiesto. Se elige un archivo y no la memoria de la conversación del orquestador porque el conteo tiene que ser el mismo con dobles en `pytest` que con el modelo real, y la conversación no es testeable. INV-06 se mantiene: nada de lo que hay en el cursor entra en ningún artefacto de la novela.

No hay estado `abortado`. Un fallo que detiene la tanda (EX-01, EX-03, EX-04, EX-08) deja el manifiesto en `en_progreso` con `ultimo_error` relleno; `status` lo muestra y la siguiente tanda arranca desde el último capítulo cerrado, que es lo que INV-07 pide. Un estado extra no aportaría información que `ultimo_error` no dé.

### 5.1 Registro de ejecución (`07_registro/`)

Implementa RF-08.5. El manifiesto dice **dónde está** la novela; el registro dice **qué pasó** para llegar ahí. Son cosas distintas y por eso son archivos distintos: el manifiesto se lee entero en cada arranque y tiene que seguir siendo corto, mientras que el registro crece sin límite y solo se abre cuando hay algo que auditar.

Una carpeta por tanda, nombrada con la marca de tiempo de su inicio:

```
07_registro/
└── tanda_2026-09-16T12-40-03/
    ├── eventos.jsonl        # append-only, una línea por evento, en orden
    ├── cursor.json          # copia final del cursor: tope, cerrados, motivo de salida
    ├── prompts/             # el contexto exacto entregado a cada agente en cada invocación
    ├── retornos/            # el mensaje final textual de cada subagente
    ├── descartados/         # borradores y deltas rechazados, con el error que los rechazó
    └── uso.jsonl            # consumo por invocación (H-10)
```

`eventos.jsonl` lleva una línea por hecho observable, siempre con `ts`, `tipo` y, cuando aplique, `capitulo`:

| `tipo` | Lo escribe | Campos propios |
|---|---|---|
| `verbo` | el CLI, al terminar cada verbo | `verbo`, `args`, `resultado`, `ms` |
| `agente_inicio` / `agente_fin` | `subagent_stop.py` y el verbo que prepara la invocación | `rol`, `agent_id`, `turnos`, `intentos_de_validacion` |
| `hook` | cada script de hooks | `id` (H-xx), `agent_type`, `accion`, `decision` (`permitido`/`bloqueado`/`verificado`/`falla`), `motivo` |
| `validacion` | los verbos `validar-*` | `rol`, `artefacto`, `valido`, `errores` |
| `error` | quien detiene la tanda | `excepcion`, `mensaje`, `traza` |

Reglas de implementación:

- Escriben los scripts y los hooks. El orquestador no escribe aquí: H-09 le bloquea también esta carpeta, igual que el manuscrito.
- `07_registro/` no es estado de la novela. Se versiona porque hace la corrida revisable, pero borrarlo no cambia el manuscrito ni un solo artefacto de `04_estado/`. Es la diferencia con `.tanda/`, que además desaparece al terminar.
- `uso.jsonl` se mueve aquí desde `04_estado/`: es evidencia de la ejecución, no memoria de la obra.
- `04_estado/prompts/` y `04_estado/deltas/` siguen siendo el área de trabajo de la tanda en curso, que se sobrescribe; su **copia** del momento de la invocación es la que queda en el registro. Sin esa copia no hay forma de saber qué recibió de verdad un agente, porque el archivo de trabajo ya fue pisado por el capítulo siguiente.
- `status` (§8.2) lee el registro de la última tanda: muestra el manifiesto y, debajo, los últimos eventos y cualquier `error` sin cerrar.

## 6. Orquestador — mapeo del loop a módulos

Pseudocódigo del loop. Lo ejecuta la skill `/escribir-tanda` (§13.2), que llama a los helpers deterministas de `orchestrator/loop.py` para todo lo que no sea generación. Las tres llamadas a agentes — `escritor.generar_capitulo`, `extractor.extraer`, `qa.ejecutar_corte` — son **invocaciones de subagente**, no llamadas HTTP: Python ensambla el contexto y parsea la respuesta; Claude Code hace la llamada al modelo (§3). En la implementación el loop no es una función que corre de una vez: la skill lo avanza tramo a tramo con los verbos internos de §8.2, porque entre un tramo y el siguiente hay una invocación de subagente que solo el orquestador puede hacer. El pseudocódigo fija el orden y las reglas; los verbos son sus tramos. Cada paso anotado al requisito funcional que implementa:

```python
def ejecutar_tanda(config: HarnessConfig, capitulos_por_tanda: int | None = None):
    # El argumento pisa al del archivo de configuración (RF-CFG-03);
    # ningún otro parámetro admite override por línea de comandos.
    tope = capitulos_por_tanda or config.capitulos_por_tanda

    estado = checkpoint.leer_estado()                       # §5
    if estado == "pausado_por_qa":
        raise PausadoPorQAError()                           # EX-02, RF-07.4
    if estado == "completo":
        return ResultadoTanda(cerrados=0, motivo="completo")

    n_inicio = checkpoint.detectar_punto_de_reanudacion()   # RF-CFG-04, INV-07
    cerrados_en_esta_tanda = 0

    for n in range(n_inicio, config.total_capitulos + 1):
        if tope is not None and cerrados_en_esta_tanda >= tope:
            # Fin limpio de tanda (RF-CFG-02): no es error ni pausa.
            # El manifiesto queda en_progreso y la próxima ejecución sigue en n.
            return ResultadoTanda(cerrados=cerrados_en_esta_tanda, motivo="tope_de_tanda")

        entrada = repository.leer_outline_entry(n)         # RF-03.1
        if entrada is None:
            raise OutlineFaltanteError(n)                   # EX-03

        contexto = escritor.ensamblar_contexto(n, config)   # RF-05.1
        if contexto.tokens_estimados > config.max_tokens_contexto_escritor:
            contexto = escritor.recortar_resumen_rodante(contexto)  # EX-04
            if contexto.excede_limite():
                raise ContextoExcedidoError(n)

        borrador = escritor.generar_capitulo(contexto)      # RF-05.2, RF-05.3
        repository.guardar_capitulo(n, borrador)            # RF-05.4

        delta = extractor.extraer(n)                        # RF-06.1
        repository.aplicar_delta_personajes(delta)           # RF-06.2
        repository.aplicar_delta_continuidad(delta)           # RF-06.3
        repository.actualizar_resumen_rodante(delta)          # RF-06.4

        checkpoint.marcar_capitulo_cerrado(n)
        cerrados_en_esta_tanda += 1

        # El corte de QA corre por su propia cadencia, antes de evaluar el tope
        # de tanda: cortar la tanda nunca omite ni adelanta un QA (RF-CFG-02).
        if n % config.cadencia_qa == 0:
            reporte = qa.ejecutar_corte(n)                   # RF-07.1-07.3
            repository.guardar_reporte_qa(reporte)
            if reporte.tiene_contradicciones:
                checkpoint.pausar_por_qa(reporte)             # RF-07.4
                return ResultadoTanda(cerrados=cerrados_en_esta_tanda,
                                      motivo="pausado_por_qa")

    checkpoint.marcar_completo()
    return ResultadoTanda(cerrados=cerrados_en_esta_tanda, motivo="novela_completa")
```

Los tres motivos de salida limpia (`tope_de_tanda`, `pausado_por_qa`, `novela_completa`) se distinguen porque el usuario necesita saber si volver a invocar el harness continúa la novela o no. Solo `tope_de_tanda` deja el manifiesto listo para reanudar sin intervención.

## 7. Manejo de errores — excepciones concretas

Mapeo directo de la tabla de excepciones de la especificación funcional (§7) a clases de Python:

```python
class EstadoInvalidoError(Exception): ...      # EX-01
class PausadoPorQAError(Exception): ...        # EX-02
class OutlineFaltanteError(Exception): ...     # EX-03
class ContextoExcedidoError(Exception): ...    # EX-04
class ConfiguracionInvalidaError(Exception): ...      # EX-05
class ConfiguracionInconsistenteError(Exception): ... # EX-06
class LongitudFueraDeRangoAviso(Warning): ...         # EX-07 — aviso, no excepción: la tanda sigue
class PersonajeNoPrevistoError(Exception): ...        # EX-08 — solo tras el segundo intento fallido
class AutovalidacionFallidaError(Exception): ...      # EX-10 — el agente agotó sus intentos de validar su salida
```

EX-10 la lanza el verbo que lee el artefacto cuando el agente terminó informando que no consiguió validarlo: el artefacto se mueve a los descartados del registro (§5.1) y el fallo se trata como el de su rol — EX-01 para un delta, EX-07 o EX-08 para un borrador.

EX-07 es deliberadamente un `Warning` y no una excepción: el segundo intento fuera de rango se acepta y se anota en `intentos_por_capitulo`, nada se detiene. EX-08 sí es excepción, pero `loop.py` la lanza únicamente cuando el reintento también falla; el primer fallo se resuelve regenerando sin salir del loop.

Ninguna de estas se captura silenciosamente en `orchestrator/loop.py`: todas terminan la ejecución de la tanda y dejan el `manifest.json` en un estado consistente con lo que sí se alcanzó a cerrar.

## 8. Configuración extendida (`config/`)

La configuración vive en una **carpeta**, no en un único archivo. El inventario completo y la razón de la partición están en §11; lo que sigue es el contenido consolidado, como referencia rápida de todos los parámetros juntos.

```json
{
  "total_capitulos": 40,
  "capitulos_por_tanda": 5,
  "max_llamadas_por_tanda": null,
  "registrar_uso": true,
  "origen_estilo": "referencias",
  "palabras_por_capitulo": 3000,
  "idioma": "es-ES",
  "persona_narrativa": "tercera_limitada",
  "tiempo_verbal": "pasado",
  "ventana_resumen_rodante": 3,
  "cadencia_qa": 8,
  "max_tokens_contexto_escritor": 5000,
  "max_hechos_por_capitulo": 4,
  "proveedores": {
    "escritor":  { "provider": "openrouter", "model": "<MODELO_CAPAZ>" },
    "extractor": { "provider": "openrouter", "model": "<MODELO_ECONOMICO>" },
    "qa":        { "provider": "openrouter", "model": "<MODELO_CAPAZ>" }
  },
  "reintentos": { "max_intentos": 3, "backoff_base_segundos": 2 }
}
```

La API key de OpenRouter se lee de variable de entorno (`OPENROUTER_API_KEY`), nunca del archivo de configuración versionado.

### 8.1 Validación de los parámetros de dimensionamiento

`config.py` valida antes de cualquier llamada al modelo (EX-05), con un modelo Pydantic:

```python
class HarnessConfig(BaseModel):
    total_capitulos: int = Field(ge=30, le=50)        # RF-CFG-01, acotado por RF-03.1
    capitulos_por_tanda: int | None = Field(default=None, ge=1)  # RF-CFG-02; None = sin tope
    max_llamadas_por_tanda: int | None = Field(default=None, ge=1)  # RF-CFG-06
    registrar_uso: bool = True                        # RF-CFG-06
    origen_estilo: Literal["referencias", "descripcion"] = "referencias"  # RF-00.1
    palabras_por_capitulo: int = Field(gt=0)          # RF-CFG-01
    idioma: str                                       # RF-CFG-05
    persona_narrativa: Literal["primera", "tercera_limitada", "tercera_omnisciente"]
    tiempo_verbal: Literal["presente", "pasado"]
    ventana_resumen_rodante: int = Field(ge=1)
    cadencia_qa: int = Field(ge=1)
    max_tokens_contexto_escritor: int = Field(gt=0)
    max_hechos_por_capitulo: int = Field(gt=0)        # §11.6 — acota el crecimiento del log
```

`capitulos_por_tanda` **no** se valida contra `total_capitulos`: un tope mayor que los capítulos restantes es válido y simplemente significa "terminá la novela" (RF-CFG-02).

Al reanudar, `checkpoint.py` compara `config.total_capitulos` contra la cantidad de entradas de `capitulos.json`. Si difieren y ya hay capítulos cerrados, dispara `ConfiguracionInconsistenteError` (EX-06) en vez de reanudar — cambiar el tamaño de la obra a mitad de camino invalida la escaleta.

### 8.2 Interfaz de línea de comandos

Dos capas. La **externa** es la que teclea el usuario. La **interna** son los verbos con los que la skill `/escribir-tanda` avanza el loop de §6 tramo a tramo: entre un tramo y el siguiente hay una invocación de subagente, que solo el orquestador puede hacer, así que el loop no puede ser una sola función Python que corre de principio a fin.

```bash
# --- capa externa: la usa el usuario ---
/escribir-tanda                          # skill (§13.2): usa capitulos_por_tanda del archivo
/escribir-tanda 3                        # pisa el valor del archivo (RF-CFG-03)
/escribir-tanda --hasta-el-final         # ignora el tope y sigue hasta total_capitulos
/resolver-qa                             # skill: reextrae los capítulos pendientes (RF-07.6, paso 2)
python -m app status                 # manifiesto, cursor si existe, ultimo_error; no genera nada
python -m app resolver --reporte qa_cap_16 --capitulos 14,15
                                         # RF-07.6 paso 1: marca superados y deja reextraccion_pendiente
python -m app resolver --reporte qa_cap_16 --sin-cambios
                                         # revisé y no toqué ningún capítulo: cierra en un solo paso
python -m app resolver --cerrar      # RF-07.6 paso 3: solo si reextraccion_pendiente está vacía
python -m app ensamblar                  # concatena los capítulos cerrados con su título
                                         # en 08_entrega/novela.md
python -m app ensamblar --salida <ruta>  # la misma salida en otra ruta
python -m app exportar-traza <tanda>     # publica el registro de esa tanda en Langfuse (RF-09, §16)
python -m app exportar-traza <tanda> --con-cuerpos
                                         # incluye prompts y prosa; fuera de lo normal, §16.6
python -m app guardar <artefacto>    # fases 0-4: persiste con validación (EX-01) lo que generó la skill

# --- capa interna: la usa la skill, un tramo del loop por verbo ---
python -m app tanda iniciar [--capitulos N | --hasta-el-final]
                                         # lee el manifiesto, crea .tanda/cursor.json (§5)
python -m app preparar-capitulo N    # EX-03 a EX-06; escribe 04_estado/prompts/escritor_cap_N.md
python -m app registrar-escritor N "<línea de retorno>"
                                         # parser de RF-08.1: rechaza prosa o más de una línea
python -m app aplicar-delta N        # lee 04_estado/deltas/delta_cap_N.json; EX-01, EX-08;
                                         # cierra el capítulo y responde si toca QA
python -m app descartar-borrador N   # EX-08: borra el borrador para regenerar
python -m app preparar-qa N          # arma la muestra y las rutas permitidas del corte
python -m app cerrar-qa N            # lee qa_cap_N.json; pausa o continúa (RF-07.4)
python -m app tanda siguiente        # avanza el cursor; responde tope_de_tanda | seguir | novela_completa

# --- capa de validación: la usan los agentes, un validador por rol (RF-08.4) ---
python -m app validar-capitulo N         # escritor: longitud ±20 % y personajes del registro
python -m app validar-delta N            # extractor: esquema, sujetos, tope de hechos
python -m app validar-reporte N          # qa: esquema de ReporteQA y recursos_usados.json
```

Solo `capitulos_por_tanda` admite override. `total_capitulos` y `palabras_por_capitulo` no se exponen como argumentos a propósito: pasarlos por línea de comandos invitaría a cambiarlos entre tandas, que es justo lo que EX-06 e INV-04 buscan impedir.

Los verbos internos escriben dos carpetas auxiliares dentro de `04_estado/`: `prompts/`, con el contexto ensamblado que el orquestador copia en la invocación del escritor (el escritor no tiene `Read`, §13.1), y `deltas/`, donde el extractor escribe y valida su propio JSON (RF-08.4) para que `aplicar-delta` lo lea ya validado (H-02 lo valida además al escribirse). Son artefactos de trabajo, no de estado: se pueden borrar sin perder nada de la novela.

Los tres verbos `validar-*` son la única parte del CLI que ejecuta un agente, y siempre sobre su propio artefacto (RF-08.4). Son de solo lectura: comprueban y devuelven el error, nunca corrigen ni persisten. El que aplica sigue siendo el verbo del orquestador (`aplicar-delta`, `registrar-escritor`, `cerrar-qa`), que **vuelve a validar**: que el agente se haya validado no exime al harness de hacerlo, porque la validación del agente es una optimización del bucle, no la garantía.

**`resolver`** es la única forma legítima de salir de `pausado_por_qa`. Son tres pasos, porque la reextracción invoca al extractor y los scripts no llaman a modelos: (1) `--reporte X --capitulos a,b` verifica que el reporte sea el que figura en `reporte_qa_pendiente`, marca superados los hechos con esos `cap_origen`, fija `reextraccion_pendiente = [a, b]` y `capitulo_activo = a`, para que H-05 deje al extractor leer un capítulo anterior al actual; (2) la skill `/resolver-qa` invoca al extractor por cada capítulo pendiente y aplica cada delta con `aplicar-delta --reextraccion`, que quita el capítulo de la lista, aplica el delta nuevo sobre las fichas y regenera la sección `## Capítulo N` del resumen rodante si cae en la ventana; (3) `--cerrar` pone `reporte_qa_pendiente = null` y `estado = en_progreso` solo si la lista quedó vacía. `--sin-cambios` hace (1) y (3) de una vez: no hay nada que reextraer. Si algo falla a mitad, el manifiesto conserva la lista y se retoma donde quedó. `--sin-cambios` y `--capitulos` son mutuamente excluyentes; omitir ambos es error, porque el harness no puede adivinar qué se corrigió.

**`ensamblar`** concatena `cap_1.md` … `cap_K.md` para los K capítulos cerrados, anteponiendo a cada uno su `titulo` de `capitulos.json` como encabezado. No es exportación ni maquetación (fuera de alcance, spec funcional §2): es la forma de leer lo generado sin abrir 40 archivos. No lee ni modifica ningún artefacto de estado, así que puede correr en cualquier momento, incluso con la tanda pausada. Escribe en `08_entrega/novela.md` salvo que `--salida` diga otra cosa. Esa carpeta es salida derivada, no estado: se borra y se regenera sin perder nada, y por eso queda fuera del control de versiones. Está fuera de `05_manuscrito/` para que esa carpeta siga siendo exactamente un archivo por capítulo y nada más, y está bajo H-09 por una razón menos obvia: un ensamblado legible por el orquestador anularía INV-08 por la puerta de atrás, porque le permitiría meterse la novela entera en contexto de una sola lectura, que es justo lo que impedirle leer capítulo a capítulo pretende evitar.

## 9. Plan de pruebas

| Nivel | Qué cubre | Cómo |
|---|---|---|
| Unitarias | Cada criterio de aceptación de la especificación funcional que sea verificable sin LLM real (validación de esquemas, append-only de continuidad, recorte de resumen rodante, cálculo de reanudación). | `pytest`, sin llamadas externas. |
| Integración con agentes simulados | El loop completo de `ejecutar_tanda` para 3 capítulos, con las tres invocaciones de subagente sustituidas por dobles que devuelven respuestas fijas. | Verifica que `agents/escritor.py` nunca reciba una ruta de `05_manuscrito/`, y que el manifiesto quede consistente tras una interrupción simulada a mitad de tanda. |
| Manual, con LLM real | Corrida de 8-10 capítulos reales antes de comprometerse a una tanda completa, revisando `personajes.json` y `continuidad.json` a mano. | Revisión manual: cada hecho con su `cap_origen` correcto, ninguna ficha duplicada, resumen rodante fiel a los últimos capítulos, títulos únicos. |
| Equivalencia de tandas (INV-06) | Que partir la generación en tandas no cambie el resultado. | Con los dobles de subagente deterministas: correr 6 capítulos de una vez y, en otro directorio, correr 3 + 3. Los artefactos de estado y los `cap_*.md` deben ser idénticos byte a byte. |
| Reanudación (RF-CFG-04, INV-07) | Que reanudar avance y nunca reescriba. | Correr una tanda de 3, anotar los `mtime` de `cap_1..3.md`, correr otra tanda de 3, verificar que esos `mtime` no cambiaron y que aparecieron `cap_4..6.md`. |
| **Calidad de atribución de sujeto** (RF-06.1) | Que el filtrado de RF-05.1 se apoye en datos confiables. **Es el criterio que decide si el diseño de §12.3 se sostiene.** | Sobre los 8-10 capítulos de la corrida manual: revisar a mano cada hecho de `continuidad.json` y contar cuántos tienen el `sujeto` correcto. Medir también la proporción de `sujeto_validado = false`. |
| Cobertura del filtro (RF-05.1) | Que filtrar no omita hechos relevantes. | Para cada capítulo de la corrida manual, comparar los hechos inyectados contra el log completo y revisar si algún hecho excluido era pertinente a lo que el capítulo terminó narrando. |
| **Hooks** (RF-08.2) | Que cada script de `scripts/hooks/` bloquee o verifique exactamente lo que dice §13.3. | `pytest` ejecuta cada script con un payload JSON simulado por stdin, con el mismo formato que envía Claude Code (`hook_event_name`, `tool_name`, `tool_input`, `agent_type`), y comprueba código de salida y mensaje. Ejemplos: un `Read` con `agent_type = extractor` sobre `cap_3.md` cuando el capítulo actual es el 5 sale con código 2; una escritura de `continuidad.json` que pierda un hecho falla; un `Agent` con `agent_id` presente sale con código 2. Sin modelo. |
| Contrato de retorno (RF-08.1) | Que el mensaje final de cada subagente respete su forma. | Con dobles: el parser de `agents/escritor.py` rechaza un retorno multilínea o con más de ~40 palabras. En la corrida manual: guardar el mensaje final del escritor de cada capítulo y verificar que es una línea sin prosa. |
| **H-11, el hook crítico** (RF-08.4) | Que `Bash` en los tres agentes sirva solo para validar. **Es la prueba que más importa de la suite**: si H-11 falla, los tres agentes tienen shell libre y caen INV-01 e INV-02. | `pytest` con payloads simulados. Casos que deben salir con código 2: `cat 05_manuscrito/cap_1.md`; `python -m app validar-capitulo 3` cuando el capítulo de la invocación es el 5; `python -m app validar-capitulo 5; cat cap_1.md`; `python -m app validar-capitulo 5 && ls`; `echo $(cat cap_1.md)`; `python -m app validar-delta 5` con `agent_type = escritor`; `python -m app status`. Debe salir con 0: exactamente el validador del rol con el capítulo correcto. |
| Autovalidación (RF-08.4) | Que el validador que corre el agente sea el mismo código que corre el harness. | `pytest`: `validar-delta` sobre un delta con sujeto fuera del registro devuelve el mismo error que `aplicar-delta`; `validar-capitulo` sobre un borrador corto devuelve el mismo desvío que calcula EX-07. Un agente no puede aprobarse con otro criterio. |
| Registro de ejecución (RF-08.5) | Que una tanda deje reconstruible lo que pasó. | Con dobles: correr 3 capítulos y comprobar que `eventos.jsonl` contiene, en orden, los verbos, los pares `agente_inicio`/`agente_fin` de los seis subagentes, los hooks disparados y ningún hueco; que `prompts/` y `retornos/` tienen un archivo por invocación; y que una tanda interrumpida a mitad deja un evento `error` con traza. |
| Observabilidad (RF-09) | Que la traza refleje la tanda y que exportar dos veces no duplique. | Sin red: un doble del cliente que acumula lo enviado. Se comprueba que las cuatro cifras de tokens de §16.3 viajan (no solo entrada y salida), que una segunda exportación de la misma tanda no crea una traza nueva, y que con los valores por defecto ninguna subcadena del manuscrito ni de los prompts aparece en lo enviado. |
| Antirrepetición (RF-05.5) | Que una repetición literal se rechace y que los recursos agotados lleguen al prompt. | Sin modelo: se construyen dos capítulos con una frase de contenido compartida y se comprueba que `validar-capitulo` la nombra junto a su capítulo de origen; y que `preparar-capitulo` incluye la lista de recursos con su conteo. Se comprueba además que una secuencia solo de palabras vacías no dispara el rechazo. |
| Panel de fases (RF-UI-03) | Que un botón y el comando tecleado produzcan lo mismo, y que ninguno se lance fuera de su condición. | Sin modelo: los endpoints se prueban con un doble del lanzador que registra el comando en vez de ejecutarlo. Se comprueba que cada botón compone `claude -p "/<skill>"` sin `--bare`, que un botón sin condición de entrada devuelve el motivo y no lanza, y que con una ejecución viva todos quedan deshabilitados. |

Criterio de decisión para las dos filas nuevas: si la atribución de sujeto acierta por debajo de ~90%, o si aparece algún hecho pertinente excluido por el filtro, hay que volver a inyectar `continuidad.json` completo y asumir el costo de contexto. El resto del esquema (`sujeto`, `categoria`, `superado_por`) se conserva igual: sigue sirviendo para QA y para RF-07.6 aunque el escritor no filtre.

## 10. Trazabilidad requisito → componente técnico

| Requisito funcional | Componente técnico |
|---|---|
| RF-05.1 (ensamblado de contexto) | `agents/escritor.py::ensamblar_contexto` (helper determinista, único punto que decide qué rutas entran) + subagente `.claude/agents/escritor.md` sin herramienta `Read` |
| RF-05.3 (restricción de acceso del escritor) | Regla de dependencias §2 — `escritor.py` no importa lectura de manuscrito |
| RF-06.1 (extracción de un solo capítulo) | `agents/extractor.py::extraer` — firma solo acepta `cap_n: str`, no una lista |
| RF-06.3 (continuidad append-only) | `state/continuidad.py::aplicar_delta` — solo expone `agregar()` y `marcar_superado()`, sin `eliminar()` ni `modificar()` |
| RF-05.1 (filtrado por relevancia) | `state/continuidad.py::filtrar_para_capitulo(entrada_outline)` — devuelve una selección de lectura; no escribe |
| RF-06.1 (registro de sujetos) | `state/personajes.py::sujetos_conocidos()` + validador Pydantic sobre `HechoContinuidad.sujeto`; un sujeto fuera del registro fija `sujeto_validado = False`, no rechaza el hecho |
| RF-07.6 (reextracción tras corrección) | `state/continuidad.py::marcar_superado(caps)` — fija `superado_por`, nunca borra (INV-03) |
| RF-07.4 (resolución como operación) | `cli.py::resolver` — único código que pone `reporte_qa_pendiente = null`; `checkpoint.py` rechaza reanudar si el campo no es nulo con `estado = en_progreso` (§5, §8.2) |
| RF-03.1 (títulos en fase 3) | `schemas/outline.py::EntradaOutline.titulo` + validador de unicidad sobre el array completo |
| RF-05.1 (tensión como objetivo) | `agents/escritor.py::ensamblar_contexto` — inyecta `entrada.tension` junto al vocabulario de ritmo de `style_guide.md` |
| EX-07 (longitud fuera de rango) | `orchestrator/loop.py` — un reintento con el desvío como feedback, luego `LongitudFueraDeRangoAviso` y `intentos_por_capitulo[n] = 2` |
| EX-08 (personaje no previsto) | `orchestrator/loop.py` — detecta en `delta.personajes` una clave ausente del registro de sujetos, regenera; al segundo fallo lanza `PersonajeNoPrevistoError` |
| RF-00.2 (verificación contra referencias) | `tests/test_referencias.py` — lee `00_referencias/`; si la carpeta no existe, `pytest.skip` con motivo explícito, nunca pasa en silencio |
| Ensamblado (spec funcional §2) | `cli.py::ensamblar` — solo lee `05_manuscrito/` y `capitulos.json`; no toca estado |
| RF-07.4 (pausa ante contradicciones) | `orchestrator/checkpoint.py::pausar_por_qa`, estado `pausado_por_qa` en el manifiesto |
| RF-CFG-01 (dimensionamiento) | `config.py::HarnessConfig` — §8.1, rangos validados con Pydantic |
| RF-CFG-02 (tanda parcial) | `orchestrator/loop.py::ejecutar_tanda` — contador `cerrados_en_esta_tanda`, salida `tope_de_tanda` |
| RF-CFG-03 (precedencia CLI) | `cli.py` — solo `--capitulos` pisa el archivo; ningún otro parámetro se expone |
| RF-CFG-04 (reanudación entre tandas) | `orchestrator/checkpoint.py::detectar_punto_de_reanudacion` |
| INV-06 (la partición en tandas no altera el estado) | El conteo de tanda vive en memoria; el manifiesto no lo registra — §5 |
| INV-07 (no se regenera un capítulo cerrado) | El loop arranca en `ultimo_capitulo_cerrado + 1`; `guardar_capitulo` falla si el archivo ya existe |
| EX-01 (estado inválido) | `state/repository.py` — validación Pydantic previa a cualquier escritura |
| EX-04 (contexto excedido) | `agents/escritor.py::recortar_resumen_rodante`, nunca toca `continuidad.json` ni `personajes.json` |
| INV-05 (QA único con acceso amplio al manuscrito) | Solo `agents/qa.py` importa `repository.leer_muestra_manuscrito`; ningún otro módulo de `agents/` lo hace |

### 10.1 Invariante → mecanismo de cumplimiento

Cada invariante tiene asignado **con qué** se hace cumplir (RF-08.2). "Prompt" o "CLAUDE.md" solos no cuentan como mecanismo: son intención. Los identificadores H-xx son los hooks de §13.3.

| Invariante | Allowlist del agente | Hook | Código | Límite documentado (§13.6) |
|---|---|---|---|---|
| INV-01 escritor sin manuscrito | `escritor.md` sin `Read`, `Grep`, `Glob` | H-06 limita su `Write` a `cap_N.md`; H-11 limita su `Bash` al validador | `ensamblar_contexto` es el único ensamblador | — |
| INV-02 extractor, un capítulo | `extractor.md` sin `Grep`, `Glob` | H-05 bloquea `Read` fuera de `cap_N.md`; H-11 acota su `Bash` | firma `extraer(cap_n)` | — |
| INV-03 trazabilidad, append-only | — | H-03 verifica superconjunto tras `Write` | `continuidad.py` sin `eliminar()` | — |
| INV-04 esquemas y `novela.json` inmutables | — | H-04 bloquea `Write`/`Edit` sobre `config/novela.json` con capítulos cerrados | EX-06 en `checkpoint.py` | cambiar el código de los esquemas: revisión humana |
| INV-05 solo QA lee varios | solo `qa.md` lleva `Grep`, `Glob` | H-06 bloquea `Write` en `05_manuscrito/` a extractor y QA | solo `qa.py` importa la muestra | — |
| INV-06 tandas no alteran estado | — | — | conteo en memoria; test de equivalencia §9 | — |
| INV-07 no regenerar cerrados | — | — | `guardar_capitulo` falla si el archivo existe | — |
| INV-08 orquestador fuera del manuscrito | — | H-09 bloquea `Read`, `Grep`, `Glob` sobre `05_manuscrito/`, `07_registro/` y `08_entrega/` en la sesión principal | `status` detecta manifiesto inconsistente | edición de estado vía `Bash`: solo `CLAUDE.md` |
| INV-09 un solo nivel | `disallowedTools: Agent, Skill` en los tres | H-08 bloquea `Agent` cuando hay `agent_id` | — | — |

## 11. Inventario de configuración

Esta sección es el listado completo de lo que el harness necesita para correr. Todo parámetro que un agente implementador pudiera verse tentado de hardcodear debe estar acá.

### 11.1 Estructura: `config/` es una carpeta, no un archivo

La configuración se parte en archivos por responsabilidad. Un único `harness.config.json` mezcla decisiones que cambian a ritmos muy distintos: la voz narrativa se fija una vez por novela, los proveedores se tocan cuando cambia el presupuesto, y los prompts se iteran a diario.

```
config/
├── novela.json         # RF-CFG-01, RF-CFG-05 — inmutable durante la tanda
├── ejecucion.json      # RF-CFG-02, RF-CFG-06 — se cambia entre tandas
├── proveedores.json    # modelos y reintentos
└── prompts/
    ├── escritor.md
    ├── extractor.md
    └── qa.md
```

Regla que justifica la partición: `novela.json` está bajo INV-04 (no cambia con capítulos cerrados) y `ejecucion.json` está explícitamente pensado para cambiar entre tandas. Tenerlos en archivos separados hace que la validación de EX-06 sea un diff de un solo archivo, y hace visible en el control de versiones cuándo alguien tocó algo que no debía.

### 11.2 `novela.json` — inmutable durante la tanda

| Parámetro | Tipo | Requisito | Nota |
|---|---|---|---|
| `total_capitulos` | int 30–50 | RF-CFG-01 | Acotado por RF-03.1 |
| `palabras_por_capitulo` | int > 0 | RF-CFG-01 | Tolerancia ±20% (RF-05.2) |
| `idioma` | string | RF-CFG-05 | p. ej. `es-ES` |
| `persona_narrativa` | enum | RF-CFG-05 | `primera` \| `tercera_limitada` \| `tercera_omnisciente` |
| `tiempo_verbal` | enum | RF-CFG-05 | `presente` \| `pasado` |
| `ventana_resumen_rodante` | int ≥ 1 | RF-06.4 | En capítulos |
| `cadencia_qa` | int ≥ 1 | RF-07.1 | En capítulos |
| `max_tokens_contexto_escritor` | int > 0 | RF-05.1 | Ver §11.6 sobre el presupuesto real |
| `max_hechos_por_capitulo` | int > 0 | §11.6 | **Parámetro nuevo**; sin él `continuidad.json` crece sin techo |

### 11.3 `ejecucion.json` — se cambia entre tandas

| Parámetro | Tipo | Requisito |
|---|---|---|
| `capitulos_por_tanda` | int > 0 o null | RF-CFG-02 |
| `max_llamadas_por_tanda` | int > 0 o null | RF-CFG-06 |
| `registrar_uso` | bool | RF-CFG-06 |
| `origen_estilo` | `"referencias"` o `"descripcion"` | RF-00.1 |

`origen_estilo` decide de dónde sale `style_guide.md` en la fase 0 y **no admite un tercer comportamiento implícito**: con `referencias` y `00_referencias/` vacía la fase falla con el motivo, y con `descripcion` la guía se deriva de `01_concepto/idea.md` ignorando la carpeta aunque tenga textos. No hay respaldo automático de un modo al otro, porque un respaldo silencioso produce guías genéricas que nadie sabe explicar semanas después. Vive en `ejecucion.json` y no en `novela.json` porque solo tiene efecto antes del capítulo 1, así que INV-04 no lo alcanza.

### 11.4 `proveedores.json`

| Parámetro | Nota |
|---|---|
| `escritor.provider` / `.model` / `.temperature` | Modelo capaz. La temperatura del escritor es el único parámetro de muestreo que importa para la prosa |
| `extractor.provider` / `.model` / `.temperature` | Modelo económico. Temperatura baja: la tarea es estructurada |
| `qa.provider` / `.model` / `.temperature` | Modelo **capaz** (decisión en §1 y §11.7). Temperatura baja: juzga, no crea |
| `reintentos.max_intentos` / `.backoff_base_segundos` | §3.3 |

`temperature` queda documentada pero **no se aplica** en esta ruta: Claude Code no expone parámetros de muestreo por subagente. Se conserva por si alguna vez hay otra vía de acceso.

Las claves de API se leen siempre de variables de entorno, nunca de estos archivos.

### 11.5 `config/prompts/` — los prompts son artefactos versionados

Los prompts de los tres agentes viven en archivos, no embebidos en el código Python. Razón: son lo que más se itera, y si están en el código cada ajuste de redacción es un commit de código con diff ilegible. En archivos, el diff muestra exactamente qué instrucción cambió entre una tanda y la siguiente.

El manifiesto registra el hash del prompt usado por cada rol al iniciar la tanda (`prompts_hash`, §5). Si un capítulo sale mal, se puede saber con qué versión del prompt se generó.

**Qué fija esta spec y qué no.** El texto de los prompts no se especifica: se itera contra corridas reales y cualquier redacción escrita ahora va a cambiar. Lo que sí se fija es el **checklist de contenido obligatorio** de cada uno, para que un prompt se revise contra una lista y no por gusto. Un prompt que omita cualquier ítem de su lista no está listo, por bien que lea.

`prompts/escritor.md` debe llevar:
- Voz narrativa: `idioma`, `persona_narrativa`, `tiempo_verbal` (RF-CFG-05)
- La entrada de outline completa: `titulo`, `objetivo_narrativo`, `personajes`, `locacion`, `informacion_nueva` (RF-03.1)
- `tension` como objetivo explícito, con referencia al vocabulario de ritmo de `style_guide.md` (RF-05.1)
- Los hechos filtrados de continuidad, ya seleccionados por el harness — el prompt los recibe, no los elige (RF-05.1)
- El resumen rodante (RF-06.4)
- Las fichas de los personajes presentes en el capítulo (RF-04.1)
- Longitud objetivo y tolerancia: `palabras_por_capitulo` ±20% (RF-05.2)
- Prohibición explícita de introducir personajes ausentes del outline y de `personajes.json` (RF-05.2, EX-08)
- Y en el reintento de EX-07, el desvío concreto del intento anterior

`prompts/extractor.md` debe llevar:
- El texto de `cap_N.md`, y nada más del manuscrito (INV-02)
- El registro de sujetos: nombres de personajes, locaciones y el literal `mundo` (RF-06.1)
- El esquema JSON de `DeltaExtraccion` con `sujeto` y `categoria` por hecho (§4)
- Instrucción de emitir **solo lo que el capítulo establece de nuevo**, no lo que reitera
- El tope `max_hechos_por_capitulo` y el criterio para elegir cuáles (§11.6)
- Formato de `resumen_corto`: 3–5 líneas, y que las claves de `personajes` salgan del registro

`prompts/qa.md` debe llevar:
- El log de continuidad completo, con `superado_por` visible para ignorar los superados (RF-07.2)
- `recursos_usados.json` tal como quedó del corte anterior (RF-07.5)
- La muestra de capítulos (RF-07.1)
- La voz narrativa, para detectar capítulos que la rompan (RF-CFG-05)
- Instrucción de citar `cap_origen` en cada contradicción (RF-07.2)
- El umbral de repetición: "3 o más veces" (RF-07.3)
- El esquema de `ReporteQA` y la obligación de devolver `recursos_usados.json` actualizado (RF-07.5)

### 11.6 Parámetros ausentes detectados al dimensionar

**`max_hechos_por_capitulo`.** El presupuesto de `max_tokens_contexto_escritor` se consume mayoritariamente por `continuidad.json`, que es append-only y por tanto el único componente del contexto que crece sin techo. Con 4 hechos por capítulo a ~25 tokens cada uno, el log llega a ~3.900 tokens en el capítulo 40 y el contexto total supera los 5.000 configurados. La válvula de escape de EX-04 (recortar el resumen rodante) libera unos 350 tokens: es más chica que la fuga. El esquema de `DeltaExtraccion` acepta hoy `hechos_nuevos: list[HechoContinuidad]` sin tope, así que nada limita el crecimiento salvo la esperanza de que el extractor sea conciso.

La mitigación adoptada es el **filtrado por relevancia** de RF-05.1: el escritor recibe solo los hechos de las entidades que aparecen en su capítulo, más los de mundo. Con eso el log puede crecer sin techo sin que el contexto se mueva, porque lo que crece es justamente lo que no se inyecta. Ver §12.3.

`max_hechos_por_capitulo` queda como **segunda línea de defensa**, no como mecanismo principal:

1. Acota el tamaño del archivo en disco y el contexto de QA, que sí recibe el log completo.
2. Protege contra un extractor que se desborde en un capítulo puntual.

Conviene igualmente subir `max_tokens_contexto_escritor` a ~12.000: sigue siendo un orden de magnitud menos que el manuscrito y da margen para que el filtro incluya de más sin abortar, que es su comportamiento deseado ante un fallo de clasificación.

### 11.7 Decisiones abiertas

| Tema | Estado |
|---|---|
| Modelo del agente QA | **Resuelto: modelo capaz** (§1, §11.4). Con una corrección al razonamiento que circuló antes: "corre solo 5 veces" era engañoso. QA lee ~37.000 tokens por corte × 5 cortes ≈ **185.000 tokens de entrada**, contra ~200.000 del escritor (40 × 5.000). Moverlo al capaz **duplica aproximadamente el gasto en modelo caro**; no es un redondeo. Se asume igual porque un falso negativo de QA es el peor fallo del sistema: la contradicción sigue viva y el escritor construye encima durante 8 capítulos más. Si el presupuesto aprieta, la optimización es **escalar**: el económico marca candidatos en una primera pasada y el capaz juzga solo los marcados. Se difiere hasta la corrida de validación de §9, cuando se sepa cuántos candidatos marca de verdad. |
| `mundo.json` | **Resuelto por §12.3.** Sus locaciones alimentan el registro de sujetos de RF-06.1 y la clave de filtrado de RF-05.1, así que ya no es un artefacto huérfano. Su *contenido* sigue sin inyectarse al escritor, y es correcto: las reglas del universo que deben condicionar la escritura viven como hechos de `categoria = "mundo"` en `continuidad.json` (RF-04.3), que sí se inyectan siempre. `mundo.json` queda como registro de locaciones y referencia humana. |
| Selección entre borradores | **Limitación aceptada.** Fuera de alcance por decisión explícita (§2 de la spec funcional). Es la diferencia principal contra Re3, que genera varias continuaciones y rerankea por coherencia. No se revisa hasta tener una novela completa que leer: sin eso no hay forma de saber si el borrador único es el cuello de botella. |
| Deduplicación de hechos | **Limitación aceptada.** Si "la escotilla 4 quedó sellada" se extrae en el capítulo 7 y otra vez en el 9, el log tiene dos entradas. Deduplicar automáticamente es riesgoso: dos hechos parecidos pueden diferir en algo que importa, y equivocarse borra memoria. El filtrado de RF-05.1 absorbe el sobrecosto en contexto. A lo sumo QA lo reporta como hallazgo de tipo `repeticion`; nunca lo corrige solo. |

### 11.8 Skills de dominio por agente y scripts de hooks

Dos grupos de archivos que no son configuración de la novela pero sin los cuales el harness no corre, y que por eso van en el inventario.

**Skills de dominio.** Cada agente precarga una skill con su campo `skills:` (§13.1). Es conocimiento **estable del rol**, el mismo para todos los capítulos; se distingue del prompt de invocación de `config/prompts/<rol>.md`, que es la **plantilla variable** que el helper rellena con los datos del capítulo. La regla para decidir dónde va algo: si cambia entre capítulos, al prompt; si no, a la skill.

| Skill | Agente | Contenido |
|---|---|---|
| `.claude/skills/prosa-terror-espacial/SKILL.md` | escritor | Técnica de prosa del subgénero: manejo de ritmo, sugestión antes que exposición, cómo escribir aislamiento y escala. No es la guía de estilo de la novela (`style_guide.md` va en el prompt); es oficio general. |
| `.claude/skills/formato-delta/SKILL.md` | extractor | El esquema `DeltaExtraccion` con dos ejemplos completos, uno correcto y uno con los errores típicos anotados: sujeto fuera del registro, hecho reiterado en vez de nuevo, resumen largo. |
| `.claude/skills/criterios-qa/SKILL.md` | qa | Qué cuenta como contradicción y qué no (un personaje que miente no contradice el log), el umbral de repetición, cómo citar `cap_origen`, y el formato de `recursos_usados.json`. |

Las tres entran en `prompts_hash` (§5) junto con `config/prompts/`: si un capítulo sale mal, se sabe con qué versión de ambas cosas se generó.

**Scripts de hooks.** Un script por evento en `scripts/hooks/`, invocado por `.claude/settings.json` (§13.3). Cada uno lee el payload JSON por stdin, decide por `agent_type` y por la ruta afectada, e importa `app/` para validar. No tienen lógica propia de negocio: la delegan al paquete, para que la misma regla que aplica el hook sea la que prueba `pytest`.

```
scripts/hooks/
├── session_start.py      # H-01
├── pre_tool_use.py       # H-04, H-05, H-06, H-08, H-09, H-11 + copia previa de continuidad.json para H-03
├── post_tool_use.py      # H-02, H-03
└── subagent_stop.py      # H-07, H-10
```

## 12. Gestión de contexto — los archivos como memoria

El harness no tiene memoria de sesión: cada invocación de un agente nace y muere. Lo único que persiste son archivos. Esta sección clasifica cada archivo por el rol de memoria que cumple, porque de eso depende su política de actualización.

### 12.1 Clasificación

| Archivo | Rol de memoria | Política de escritura | Crece |
|---|---|---|---|
| `style_guide.md` | Larga — inmutable | Escrito una vez en fase 0 | No |
| `tres_actos.md` | Larga — inmutable | Escrito una vez en fase 2 | No |
| `capitulos.json` | Larga — inmutable | Escrito una vez en fase 3 (INV-04) | No |
| `mundo.json` | Larga — inmutable | Escrito una vez en fase 4 | No |
| `personajes.json` | Larga — mutable | Sobrescritura por personaje (RF-06.2) | Casi no |
| `continuidad.json` | Larga — acumulativa | Append-only (RF-06.3, INV-03) | **Sí, sin techo** |
| `recursos_usados.json` | Larga — acumulativa | Escrito por QA en cada corte (RF-07.5) | Sí, lento |
| `resumen_rodante.md` | **Corta** | Ventana deslizante (RF-06.4) | No, por diseño |
| `manifest.json` | Control, no memoria narrativa | Sobrescritura | No |
| `05_manuscrito/cap_*.md` | **No es memoria** — es la salida | Append de archivos nuevos | Sí, rápido |

La distinción que importa: **memoria larga** responde "qué es verdad en esta novela"; **memoria corta** responde "dónde quedó la escena". La primera no puede perder información sin producir contradicciones; la segunda está diseñada para olvidar, y ese olvido es el que mantiene plano el costo por capítulo.

El manuscrito no es memoria de ningún tipo. Es el producto. Que no se relea es la decisión central del diseño, no una limitación.

### 12.2 Qué entra al contexto de cada agente

| Agente | Memoria larga | Memoria corta | Manuscrito |
|---|---|---|---|
| Escritor | style_guide, tres_actos, capitulos[N], personajes, **continuidad filtrada** (RF-05.1) | resumen_rodante | **Ninguno** (INV-01) |
| Extractor | solo el **registro de sujetos** — nombres, sin hechos | ninguna | Solo `cap_N.md` (INV-02) |
| QA | continuidad completo, recursos_usados | ninguna | Últimos `cadencia_qa` capítulos (INV-05) |
| Orquestador | ninguna: solo los retornos de los agentes (RF-08.1) y la salida de `status` (H-01) | ninguna | **Ninguno** (INV-08, H-09) |

El extractor no recibe memoria narrativa a propósito: si viera el estado acumulado, tendería a repetir hechos ya registrados en vez de extraer solo lo nuevo del capítulo. El registro de sujetos es la única excepción, y es deliberadamente un **vocabulario** — la lista de nombres canónicos de personajes y locaciones, sin sus estados ni sus hechos. Sirve para que el extractor nombre las entidades igual que el resto del sistema, no para que recuerde qué les pasó.

QA es el único que recibe el log completo: su trabajo es precisamente buscar contradicciones contra todo lo establecido, no escribir la escena siguiente.

### 12.3 Estructura del log de continuidad — decisión adoptada

`HechoContinuidad` lleva un `sujeto` canónico y una `categoria`, además de la formulación en prosa. El esquema vinculante está en §4.

**Qué se evaluó.** La literatura usa estructuras más ricas: DOME almacena su memoria de largo plazo como cuádruplas `<sujeto, acción, objeto, capítulo>` y agrupa hechos por reglas mecánicas antes de consultar al modelo.

Se descartó adoptar `accion` y `objeto`. Esas reglas comparan cadenas, y solo funcionan si las tripletas están canonicalizadas. Canonicalizar el sujeto es tratable porque hay un registro cerrado de personajes y locaciones; canonicalizar la acción no lo es, porque el vocabulario de verbos en prosa es abierto: `<Kovacs, perdió, brazo izquierdo>` en el capítulo 7 y `<el capitán, tiene, ambos brazos>` en el 30 no disparan ninguna regla, porque ni el sujeto ni la acción coinciden como texto. El resultado sería estructura sin poder de detección, más dos campos que el extractor rellena y nadie puede usar.

La decisión es aditiva: si la experiencia muestra que hacen falta, `accion` y `objeto` se agregan después sin romper lo ya escrito. Quitarlos de un log append-only con doscientas entradas sería la migración cara.

**Para qué sirve `sujeto` realmente.** Menos para detectar contradicciones que para **filtrar**, y eso resuelve dos problemas con un solo campo.

`capitulos.json` ya trae por capítulo los campos `personajes` y `locacion`: la clave de recuperación ya existía en la escaleta. RF-05.1 la usa para inyectar al escritor solo los hechos de las entidades que aparecen en el capítulo N, más todos los de `categoria = "mundo"`.

Eso ataca el crecimiento sin techo de `continuidad.json` dentro del presupuesto de contexto de forma **estructural, no por recorte**: el log puede llegar a cuatrocientos hechos sin que el contexto del escritor se mueva, porque lo que crece es lo que no se inyecta. Es una mejora cualitativa sobre `max_hechos_por_capitulo` (§11.6), que limitaba cuánto se registra; el filtro no limita nada, solo selecciona.

Para QA el mismo índice acota la búsqueda a los hechos de las entidades presentes en la muestra.

**Un defecto que además corrige.** `delta.personajes` es un diccionario con nombres de personaje como claves, y el extractor no recibía ningún estado. Nada le impedía devolver `"el capitán"` donde `personajes.json` tiene `"Kovacs"`, creando una ficha duplicada que ningún criterio de aceptación detectaba. El registro de sujetos de RF-06.1 cierra ese hueco con el mismo mecanismo.

**Riesgo asumido y su mitigación.** El fallo propio de un filtro es la omisión silenciosa: si el capítulo 30 menciona a un personaje que la escaleta no listaba, sus hechos no se cargan y el escritor lo contradice sin que nada avise.

Por eso RF-05.1 fija que el filtro puede incluir de más pero nunca de menos:

- Los hechos de `categoria = "mundo"` entran siempre. Las reglas del universo no dependen de quién esté en escena.
- Los hechos con `sujeto_validado = false` entran siempre. Un error de clasificación del extractor degrada el ahorro de tokens, nunca la continuidad.

**Qué mediría un cambio de rumbo.** Todo esto depende de que el extractor asigne bien el `sujeto`. Si en la corrida de validación de §9 la tasa de aciertos es baja, el filtro se vuelve peligroso y conviene volver a inyectar el log completo, asumiendo el costo. §9 incorpora esa medición como criterio explícito.

### 12.4 Métricas computables para el corte de QA

RF-07.3 (repetición estilística) depende hoy de juicio del modelo. Hay una métrica barata que no necesita LLM: **entropía de n-gramas** sobre la muestra (Ent-2 en la literatura), que mide diversidad léxica y detecta repetición mecánicamente.

Conviene calcularla en cada corte y guardarla en el reporte junto a los hallazgos. Da una serie temporal: si la entropía cae corte tras corte, la prosa se está aplanando, y eso es visible antes de que un lector humano lo note.

Lo mismo con la **tasa de conflicto** (hechos en contradicción sobre hechos totales): convierte "QA encontró cosas" en un número comparable entre tandas.

## 13. Ruta de implementación principal: Claude Code

Claude Code es el orquestador del pipeline, por indicación de la dirección del proyecto. Los tres agentes son subagentes, las fases son skills, las validaciones son hooks, y el acceso a modelos es el de Claude Code enrutado a OpenRouter (§3). La ventaja no es solo ahorrarse un harness completo: **algunos invariantes dejan de depender del prompt y pasan a ser configuración declarativa.** Los scripts deterministas de §2 existen para cubrir con código lo que esta ruta no cubre sola (§13.6), y los hooks de §13.3 son lo que hace cumplir los invariantes sin depender del prompt (RF-08.2) y lo que acota el `Bash` que RF-08.4 obliga a dar a los tres agentes.

### 13.1 Mapeo de los tres agentes a subagentes

Un subagente de Claude Code se define en `.claude/agents/<nombre>.md`: frontmatter YAML con su configuración y el system prompt en el cuerpo. Arranca con contexto aislado: no ve la conversación principal ni los archivos que ya se leyeron. Cada agente es **un archivo**, no una carpeta: sus skills viven en `.claude/skills/` (§11.8) y sus hooks en `.claude/settings.json` (§13.3), que los aplica por agente gracias a que Claude Code informa `agent_type` en cada evento.

Los campos que interesan: `tools` (allowlist), `disallowedTools` (denylist), `model` (alias que §3.2 resuelve a OpenRouter), `skills` (skills precargadas en el contexto al arrancar) y `maxTurns` (tope de turnos, para que un agente que se traba no consuma cuota indefinidamente). Con `tools` y `disallowedTools`, INV-01, INV-02, INV-05 e INV-09 se vuelven configuración.

**Los tres agentes llevan `Bash`, y no es una relajación.** RF-08.4 exige que cada uno valide su salida antes de terminar, y validar es ejecutar el mismo comando determinista que ejecutará después el harness. El campo `tools` **no acepta comandos acotados**: `Bash(python -m app validar-delta *)` en una allowlist o en una denylist afecta a la herramienta entera, no al comando. Así que la restricción fina la pone H-11, un hook `PreToolUse` sobre `Bash` que deja pasar **únicamente** el validador del agente activo y bloquea todo lo demás. Sin ese hook, `Bash` en el escritor permitiría un `cat 05_manuscrito/cap_1.md` y rompería INV-01: la allowlist sola no basta, y por eso la ficha y el hook se diseñan juntos.

**Ficha del escritor**

```markdown
---
name: escritor
description: Redacta el borrador de un capítulo a partir del contexto ya ensamblado. Solo lo invoca /escribir-tanda.
model: opus
tools: Write, Bash
disallowedTools: Read, Grep, Glob, WebFetch, WebSearch, Agent, Skill
skills: prosa-terror-espacial
maxTurns: 8
---
```

Escribe `cap_N.md`, ejecuta `python -m app validar-capitulo N` y corrige si la longitud se sale del rango o aparece un personaje fuera del registro. `maxTurns` sube de 6 a 8 para dar sitio a esos reintentos.

El escritor **no tiene `Read`**: el helper de RF-05.1 ensambla el contexto completo y se lo entrega en el prompt de invocación. Así INV-01 no depende de que al modelo "no se le ocurra" abrir `05_manuscrito/` — no tiene con qué. `Write` lo limita H-06 a su capítulo, y `Bash` lo limita H-11 a su validador.

Tampoco lleva `memory`. La v1.2 lo tenía con `memory: project`; se quita porque una memoria que persiste entre invocaciones es un canal por el que el escritor recordaría capítulos anteriores fuera del control del harness, que es justo lo que INV-01 prohíbe. La única memoria del escritor son los artefactos de estado que el helper le inyecta.

**Ficha del extractor**

```markdown
---
name: extractor
description: Lee un único capítulo y deja su DeltaExtraccion validado en disco. Solo lo invoca /escribir-tanda.
model: haiku
tools: Read, Write, Bash
disallowedTools: Edit, Grep, Glob, WebFetch, WebSearch, Agent, Skill
skills: formato-delta
maxTurns: 8
---
```

Cambia respecto de la v1.4. Antes devolvía el JSON en su mensaje final y no tenía `Write`; ahora escribe `04_estado/deltas/delta_cap_N.json`, ejecuta `python -m app validar-delta N` y corrige hasta que valide. Gana dos cosas: el delta inválido no llega nunca al orquestador, y el JSON deja de atravesar su contexto. `Read` lo limita H-05 a su capítulo, `Write` lo limita H-06 a su archivo de delta, y `Bash` lo limita H-11 a su validador.

**Ficha de QA**

```markdown
---
name: qa
description: Corte de continuidad y estilo sobre la muestra de capítulos. Solo lo invocan /escribir-tanda y /corte-qa.
model: opus
tools: Read, Grep, Glob, Write, Bash
disallowedTools: Edit, WebFetch, WebSearch, Agent, Skill
skills: criterios-qa
maxTurns: 16
---
```

Es el único con `Grep` y `Glob` (INV-05). Escribe el reporte en sus dos formas y `recursos_usados.json` (RF-07.5), y ejecuta `python -m app validar-reporte N`; H-06 limita esa escritura a `06_qa/`.

**Lo que los tres comparten.** `Agent` y `Skill` fuera de la allowlist. Sin `Agent`, ningún agente puede lanzar subagentes: Claude Code lo permite por defecto hasta tres niveles, así que INV-09 hay que configurarlo, no viene dado. Sin `Skill`, ningún agente invoca skills por su cuenta: solo recibe la que se le precarga con `skills:`, y las skills de fase (`/escribir-tanda`, `/generar-premisa`) quedan como órdenes exclusivas del orquestador.

**Contrato de retorno (RF-08.1).** El cuerpo del `.md` de cada agente termina con la forma exacta de su mensaje final, y el helper que parsea el retorno rechaza lo que no la cumpla. Ningún artefacto viaja en el mensaje: los tres escriben en disco y devuelven una confirmación, de modo que el contexto del orquestador no acumula ni prosa, ni JSON, ni reportes.

| Agente | Devuelve | No devuelve |
|---|---|---|
| escritor | una línea: `cap_N.md · 2.940 palabras · personajes: Kovacs, Ilse · validado` | prosa, resúmenes, comentarios sobre el capítulo |
| extractor | una línea: `delta_cap_N.json · 4 hechos · 2 personajes · validado` | el JSON del delta, el texto del capítulo, explicaciones |
| qa | hasta cinco líneas: `tiene_contradicciones`, hallazgos por tipo, ruta del reporte | el reporte completo, citas largas de la muestra |

Correspondencia con los invariantes:

| Invariante | En los scripts | En Claude Code |
|---|---|---|
| INV-01 (escritor sin manuscrito) | `escritor.py` no importa `leer_manuscrito` | El subagente no tiene `Read`; H-11 impide leer por `Bash`; el único que arma su contexto es el helper |
| INV-02 (extractor, un capítulo) | Firma `extraer(cap_n: str)` | Aislamiento de contexto + H-05 sobre `Read` + H-11 sobre `Bash` |
| INV-05 (solo QA lee varios) | Solo `qa.py` importa `leer_muestra_manuscrito` | Solo `qa.md` lleva `Grep`/`Glob` |
| INV-09 (un solo nivel) | — | `disallowedTools: Agent` en los tres + H-08 |

Honestidad sobre el alcance: `tools` no restringe **qué rutas** puede leer ni **qué comandos** puede correr un agente. La restricción fina siempre la pone un hook (H-05, H-06, H-11), nunca el prompt. La garantía queda repartida en dos capas, allowlist y hook, y ninguna de las dos es "que el prompt lo pida". Corolario operativo: **si H-11 no está activo, los tres agentes tienen `Bash` sin restricción**. Es el punto más delicado de este diseño y el que sus pruebas (§9) tienen que cubrir primero.

### 13.2 Fases como skills

Cada fase del pipeline es una skill en `.claude/skills/<nombre>/SKILL.md`. Las skills admiten `context: fork` para correr en subagente, `allowed-tools` para preaprobar herramientas, y sustitución de la salida de un comando en el prompt antes de que el modelo lo vea — útil para cargar el estado sin que el modelo tenga que ir a buscarlo.

```
.claude/skills/
├── destilar-estilo/SKILL.md     # fase 0
├── generar-premisa/SKILL.md     # fase 1
├── generar-sinopsis/SKILL.md    # fase 2
├── generar-escaleta/SKILL.md    # fase 3
├── inicializar-estado/SKILL.md  # fase 4
├── escribir-tanda/SKILL.md      # fases 5-7: loop de N capítulos (RF-CFG-02), invoca los subagentes
├── corte-qa/SKILL.md            # fase 7
├── resolver-qa/SKILL.md         # RF-07.6 paso 2: reextracción tras corrección humana (§8.2)
├── prosa-terror-espacial/SKILL.md   # dominio · precargada en escritor (§11.8)
├── formato-delta/SKILL.md           # dominio · precargada en extractor (§11.8)
└── criterios-qa/SKILL.md            # dominio · precargada en qa (§11.8)
```

Las que tienen efectos irreversibles (escribir un capítulo, cerrar un corte) llevan `disable-model-invocation: true`, para que solo las dispare el usuario y no el modelo por su cuenta. Esa restricción es compatible con el panel de fases de §15.3: el botón lo pulsa el usuario, así que la orden sigue siendo suya. `/destilar-estilo` corre con `context: fork`: los textos de referencia son largos y no tienen por qué quedarse en el contexto del orquestador.

### 13.3 Hooks: el mecanismo de cumplimiento

Un hook es un comando que Claude Code ejecuta ante un evento. **Lo ejecuta Claude Code, no el agente**: el agente no lo invoca, no lo ve en su lista de herramientas y solo se entera si el hook bloquea su acción, porque recibe el motivo. Por eso es el mecanismo de RF-08.2: convierte un invariante en algo que no depende de que el modelo lo respete.

Todos los hooks del proyecto se declaran en `.claude/settings.json` y aplican a la sesión principal y a todos los subagentes. Cada evento trae en su payload `agent_type` (el nombre del subagente activo, ausente en la sesión principal) y `agent_id`, así que **un mismo script decide por agente**: la regla para el extractor no es la del escritor. Un hook bloqueante termina con código de salida 2 y el motivo por stderr; Claude Code cancela la acción y le entrega el motivo al agente. Un hook verificador que falla también sale con 2, y el orquestador trata el fallo como EX-01.

| Id | Evento y matcher | Aplica a | Qué hace | Protege |
|---|---|---|---|---|
| **H-01** | `SessionStart` | sesión principal | Ejecuta `python -m app status` y su salida entra al contexto de la sesión. La sesión nueva arranca sabiendo capítulo, estado y si hay reporte pendiente. | RF-08.3 |
| **H-02** | `PostToolUse` · `Write` sobre `04_estado/**/*.json` y `06_qa/**/*.json` | todos | Valida el archivo contra su esquema Pydantic apenas se escribe. Corre aunque el archivo se haya escrito por un camino no previsto. | EX-01 |
| **H-03** | `PostToolUse` · `Write` sobre `continuidad.json` | todos | Compara con la versión anterior: todo hecho previo debe seguir presente, con su `cap_origen`, a lo sumo con `superado_por` nuevo. Si falta uno, falla. Como `PostToolUse` ve el archivo ya sobrescrito, `pre_tool_use.py` guarda una copia en `.tanda/` antes de cada `Write` sobre `continuidad.json` y este hook compara contra ella. | INV-03, RF-06.3 |
| **H-04** | `PreToolUse` · `Write`, `Edit` sobre `config/novela.json` | todos | Bloquea si `ultimo_capitulo_cerrado > 0`. Cambiar el tamaño o la voz de la novela con capítulos cerrados invalida la escaleta. | INV-04, EX-06 |
| **H-05** | `PreToolUse` · `Read` | `agent_type = extractor` | Permite solo `05_manuscrito/cap_N.md` donde N lo resuelve `capitulo_activo()`: el campo `capitulo_activo` del manifiesto si está fijado (reextracción, §8.2), y `ultimo_capitulo_cerrado + 1` si no. Cualquier otra ruta del manuscrito, bloqueada. | INV-02 |
| **H-06** | `PreToolUse` · `Write`, `Edit` | por agente | escritor: solo `05_manuscrito/cap_N.md`, el capítulo actual. extractor: solo `04_estado/deltas/delta_cap_N.json`, su propio delta (RF-08.4). qa: solo `06_qa/`. Toda otra ruta, bloqueada. | INV-01, INV-05, RF-07.5 |
| **H-07** | `SubagentStop` · matcher `escritor` | escritor | Verifica que `cap_N.md` existe y que su longitud está en `palabras_por_capitulo ±20%`. Al primer fallo impide que el agente termine y le devuelve el desvío: es el reintento de EX-07 sin que el orquestador intervenga. Al segundo, lo deja terminar y anota el aviso en `intentos_por_capitulo`. Distingue primer y segundo fallo con `stop_hook_active` del payload. La forma de la línea de retorno no la revisa este hook sino `registrar-escritor` (§8.2). | EX-07, RF-05.2 |
| **H-08** | `PreToolUse` · `Agent` | cualquier evento con `agent_id` | Bloquea. Los subagentes no lanzan subagentes. Refuerzo de `disallowedTools: Agent`. | INV-09 |
| **H-09** | `PreToolUse` · `Read`, `Grep`, `Glob` sobre `05_manuscrito/`, `07_registro/` y `08_entrega/` | sesión principal (sin `agent_id`) | Bloquea. El orquestador no lee la novela, ni el ensamblado, ni el registro: `ensamblar` escribe el ensamblado para el usuario y `status` resume el registro. Sin `08_entrega/` en la lista, INV-08 se evadiría leyendo el ensamblado. | INV-08, RF-08.5 |
| **H-10** | `SubagentStop` · matcher `escritor\|extractor\|qa` | los tres | Lee el transcript del subagente (`agent_transcript_path` del payload), suma los tokens de **todos** los mensajes del asistente en ese transcript, no solo del último, y toma el modelo que respondió, y añade una línea a `07_registro/<tanda>/uso.jsonl` (§5.1) con rol, capítulo, modelo y tokens. Una llamada equivale a una invocación de subagente. Es la única fuente posible de RF-CFG-06: los scripts no ven el consumo de otra manera. | RF-CFG-06, §3.2 |
| **H-11** | `PreToolUse` · `Bash` | los tres agentes | Deja pasar **únicamente** el validador del agente activo: `python -m app validar-capitulo <N>` para el escritor, `validar-delta <N>` para el extractor, `validar-reporte <N>` para QA, con `N` resuelto por el mismo `capitulo_activo()` que usa H-05 para el escritor y el extractor, y por `ultimo_capitulo_cerrado` para QA, porque su corte evalúa el capítulo recién cerrado. **Los dos hooks llaman a la misma función**: dos implementaciones del mismo número acabarían divergiendo. Cualquier otro comando se bloquea, incluidas variantes con tuberías, encadenamiento (`;`, `&&`, `|`), sustitución (`$(...)`, backticks) o redirección: el script compara el comando completo contra el patrón exacto, no busca un prefijo. Es lo que hace segura la presencia de `Bash` en las tres fichas (§13.1). | INV-01, INV-02, RF-08.4 |

**Forma canónica del comando.** A lo largo de este documento los comandos se escriben `python -m app <verbo>` por brevedad, pero el intérprete real es siempre el del entorno virtual del proyecto, como fija `CLAUDE.md`. H-11 acepta **una sola forma**, la del entorno virtual, con el verbo y el número exactos y nada más. No acepta `python` a secas: en una máquina sin Python en el `PATH` ese comando no ejecutaría el validador de todos modos, así que admitirlo solo añadiría superficie sin habilitar nada. Una forma, un comando, un número.

Declaración en `settings.json`, un script por evento (§11.8):

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [{ "type": "command", "command": "python scripts/hooks/session_start.py" }] }
    ],
    "PreToolUse": [
      { "matcher": "Write|Edit|Read|Grep|Glob|Agent|Bash",
        "hooks": [{ "type": "command", "command": "python scripts/hooks/pre_tool_use.py" }] }
    ],
    "PostToolUse": [
      { "matcher": "Write",
        "hooks": [{ "type": "command", "command": "python scripts/hooks/post_tool_use.py" }] }
    ],
    "SubagentStop": [
      { "matcher": "escritor|extractor|qa",
        "hooks": [{ "type": "command", "command": "python scripts/hooks/subagent_stop.py" }] }
    ]
  }
}
```

Regla de diseño: los scripts no tienen lógica de negocio propia. Importan `app/` y llaman a la misma función que usa el CLI, para que lo que prueba `pytest` sea lo que corre el hook (§9). Un segundo choque del mismo agente contra el mismo hook en una invocación es EX-09: el script lo detecta por `agent_id` y detiene la tanda.

### 13.4 Empaquetado como plugin

Un plugin agrupa skills, agentes, hooks y servidores MCP en un directorio con manifiesto `.claude-plugin/plugin.json`. Si el flujo se estabiliza, empaquetarlo lo hace instalable y versionable:

```
novela-harness/
├── .claude-plugin/plugin.json
├── skills/          # las 7 fases + las 3 de dominio (§11.8)
├── agents/          # escritor, extractor, qa
└── hooks/hooks.json # los once hooks de §13.3
```

### 13.5 CLAUDE.md: el mapa que lee la sesión nueva

`CLAUDE.md` se carga al inicio de cada sesión, incluida la de cada subagente. Es lo primero que ve el orquestador cuando el usuario abre Claude Code en el repositorio, y por eso es donde vive el mapa completo del sistema. Junto con H-01 (estado actual inyectado), la sesión arranca sabiendo qué hay, dónde está cada cosa, en qué orden se dispara y en qué punto quedó la novela.

Contenido obligatorio, en este orden:

1. **Qué es el proyecto**, en tres líneas, y la regla de las specs: donde haya ambigüedad, detenerse y preguntar.
2. **Mapa de carpetas**: qué hay en `04_estado/`, `05_manuscrito/`, `06_qa/`, `config/`, `.claude/agents/`, `.claude/skills/`, `scripts/hooks/`, y quién puede tocar cada una.
3. **Orden de fases** y la skill que dispara cada una, de `/destilar-estilo` a `/escribir-tanda`, con la condición de entrada de cada una (qué artefacto debe existir antes).
4. **Reglas del orquestador**: INV-08 e INV-09 en una línea cada uno, más "nunca pasar rutas de `05_manuscrito/` al escritor" y "todo cambio de estado pasa por el CLI".
5. **Los invariantes INV-01 a INV-07**, una línea cada uno.
6. **Contratos de retorno** (RF-08.1): qué esperar de cada agente y qué hacer si no lo cumple: no reintentar por otra vía, reportar. Ningún agente devuelve artefactos: los escribe y los valida él mismo (RF-08.4).
7. **Dónde mira el usuario**: `status` para el estado, `07_registro/` para auditar una tanda, `ensamblar` para leer la novela.

Restricción de tamaño: cada subagente paga los tokens de `CLAUDE.md` en cada invocación. Se fija un tope de ~80 líneas; lo que no quepa va a las specs y `CLAUDE.md` lo referencia por sección.

No sustituye a las restricciones de `tools` ni a los hooks: es la capa de intención, no la de cumplimiento (RF-08.2).

### 13.6 Límites conocidos de esta ruta y cómo se compensan

| Límite | Compensación |
|---|---|
| Ejecución desatendida de una tanda larga: una sesión de Claude Code es interactiva | RF-CFG-02: la novela se escribe en tandas cortas (`/escribir-tanda 5`), cada una cabe en una sesión y el manifiesto reanuda la siguiente |
| Reintentos con backoff propios | Claude Code ya reintenta rate limits y red; el único reintento del harness es el delta inválido (§3.4) |
| Determinismo entre corridas | Todo lo que no es generación es Python puro y se prueba con `pytest` sin modelo (§9); la generación nunca fue determinista en ninguna ruta |
| Auditoría de qué archivos leyó cada agente (RF-05.3) | Allowlist de `tools` por subagente + el helper Python es el **único** que ensambla el contexto del escritor, así que qué rutas entran es código, no criterio del modelo |
| `tools` no restringe rutas dentro de `Read` | El escritor no tiene `Read`: recibe el contexto ya ensamblado en el prompt (§13.1). Sin herramienta de lectura, INV-01 no depende de que "no se le ocurra" leer |
| El orquestador podría editar estado con `Bash` (INV-08) | H-09 cubre `Read`/`Grep`/`Glob`, no `Bash`. Se acepta: el orquestador es la sesión con la que habla el usuario y cortarle `Bash` le quita el CLI. `CLAUDE.md` lo prohíbe, H-02 valida lo que escriba y `status` detecta un manifiesto inconsistente. Límite documentado, no olvido. |
| Un agente que ignora su contrato de retorno (RF-08.1) | El helper que parsea el retorno lo rechaza y el orquestador no avanza. No hay hook que lo impida antes: el mensaje final no es una herramienta. Se verifica, no se bloquea. |
| Los tres agentes tienen `Bash` (RF-08.4) | H-11 lo acota a un único comando por rol, comparando el comando completo contra el patrón exacto. Es una capa, no dos: si H-11 no corre, hay shell libre. Por eso sus pruebas encabezan §9 y `status` avisa si el hook no está declarado en `settings.json`. |

## 14. Referencias

Trabajos consultados al dimensionar la memoria y el control de continuidad:

- **DOME** — memoria de largo plazo como grafo temporal de cuádruplas, detección de conflictos por reglas, métricas Ent-2 y tasa de conflicto. <https://arxiv.org/html/2412.13575>
- **Re3** — plan, generación, reranking de continuaciones y edición por consistencia factual. Origen del patrón "plan + estado inyectado" que usa este harness. <https://arxiv.org/abs/2210.06774>
- **DOC** — control detallado del outline y desarrollo de personajes a lo largo del tiempo. <https://aclanthology.org/2023.acl-long.190.pdf>
- **Subagentes de Claude Code** — aislamiento de contexto y restricción declarativa de herramientas. <https://code.claude.com/docs/en/sub-agents>
- **Skills de Claude Code** — carga progresiva, `context: fork`, scripts embebidos. <https://code.claude.com/docs/en/skills>
- **Plugins de Claude Code** — empaquetado de skills, agentes y hooks. <https://code.claude.com/docs/en/plugins>

## 15. Frontend local (`python -m app ui`)

Pantalla web local con dos funciones: escribir los requisitos antes de la fase 0 (RF-UI-01, RF-UI-02) y lanzar las fases sin teclear comandos (RF-UI-03, RF-UI-04). No llama a ningún modelo y no orquesta nada: para lanzar una fase arranca una sesión de Claude Code, que sigue siendo el orquestador.

### 15.1 Qué recoge y qué escribe

| Sección del formulario | Requisito | Escribe en |
|---|---|---|
| Idea de la novela, texto libre | RF-01.1 | `01_concepto/idea.md` |
| Voz narrativa: `idioma`, `persona_narrativa`, `tiempo_verbal` | RF-CFG-05 | `config/novela.json` |
| Dimensionamiento: `total_capitulos`, `palabras_por_capitulo`, `ventana_resumen_rodante`, `cadencia_qa`, `max_tokens_contexto_escritor`, `max_hechos_por_capitulo` | RF-CFG-01, §11.2 | `config/novela.json` |
| Ejecución: `capitulos_por_tanda`, `max_llamadas_por_tanda`, `registrar_uso` | RF-CFG-02, RF-CFG-06 | `config/ejecucion.json` |
| Rutas locales a los ejemplos de referencia | RF-00.2 | copia a `00_referencias/` |
| Origen de la guía de estilo: ejemplos de `00_referencias/` o descripción del subgénero | RF-00.1, RF-UI-03 | `config/ejecucion.json`, campo `origen_estilo` |

La última fila es nueva y no es cosmética. Sin ella, `/destilar-estilo` se detiene a preguntar cuando `00_referencias/` está vacía, y en modo no interactivo nadie puede contestar (RF-UI-03). Toda pregunta que una skill hacía a mitad de ejecución se resuelve aquí, antes de lanzar. La casilla escribe `origen_estilo` (§11.3), y `/destilar-estilo` lo lee en vez de preguntar.

### 15.2 Reglas de la entrada

- Valida con el mismo `HarnessConfig` de §8.1 **antes** de escribir. El formulario no puede producir una configuración que el harness rechazaría: EX-05 es imposible sobre archivos escritos por esta pantalla.
- Si el manifiesto tiene `ultimo_capitulo_cerrado > 0`, los campos de `novela.json` aparecen **deshabilitados con el motivo** (INV-04, EX-06). Solo la idea y `ejecucion.json` siguen editables. Es la misma regla que RF-CFG-03 aplica a la línea de comandos, llevada a la interfaz.
- Solo biblioteca estándar: `http.server` sirviendo la página y los endpoints. Sin dependencias nuevas, sin paso de build.
- Escucha únicamente en `127.0.0.1`.

### 15.3 Panel de fases

Seis botones, uno por fase, más `ensamblar`. Cada uno lanza `claude -p "/<skill>"` con el directorio de trabajo en la raíz del proyecto y `--output-format json`, y muestra la condición que lo habilita:

| Botón | Lanza | Se habilita cuando | Coste |
|---|---|---|---|
| Destilar estilo | `/destilar-estilo` | hay textos en `00_referencias/`, o el formulario marcó la excepción de §15.1 | bajo |
| Generar premisa | `/generar-premisa` | existe `01_concepto/idea.md` | bajo |
| Generar sinopsis | `/generar-sinopsis` | existe `premisa.md` | bajo |
| Generar escaleta | `/generar-escaleta` | existe `tres_actos.md` y `config/novela.json` valida | medio |
| Inicializar estado | `/inicializar-estado` | existe `capitulos.json` | medio |
| **Escribir tanda** | `/escribir-tanda` | existen los cinco anteriores y el manifiesto no está `pausado_por_qa` | **alto** |
| Ensamblar | `python -m app ensamblar` | hay al menos un capítulo cerrado | ninguno |

El botón de ensamblar muestra la ruta de salida y el recuento de capítulos y palabras, nunca el texto: leer la novela en el navegador está fuera de alcance (§15.6).

Reglas de ejecución:

- **Nunca `--bare`.** Ese modo salta hooks, subagentes, skills y `CLAUDE.md` a propósito. Sin ellos el harness deja de ser estricto: no hay H-11, no hay allowlists, no hay invariantes. Un botón que use `--bare` es un botón que ejecuta otro sistema.
- El proceso corre en segundo plano y la página consulta el estado por su cuenta. La pantalla no se queda bloqueada durante los minutos que tarda una tanda.
- **Una ejecución a la vez** (RF-UI-03). El frontend guarda el identificador del proceso en curso y deshabilita todos los botones mientras viva. Al arrancar, si encuentra un cursor de tanda (§5) sin proceso vivo, lo informa: la ejecución anterior murió a mitad.
- El botón de la tanda abre una confirmación con `capitulos_por_tanda`, `total_capitulos` y `max_llamadas_por_tanda` antes de lanzar. Es la única acción que gasta de forma apreciable y la única que cierra capítulos.
- Las variables de entorno se heredan del proceso que arrancó el frontend, incluidas las de §3.1. El frontend **nunca** las escribe, ni las lee para mostrarlas, ni las pide por formulario: la credencial no pasa por la pantalla.
- `--output-format json` devuelve el coste estimado de cada invocación; se registra junto al evento de la fase en `07_registro/` (§5.1). Es una estimación del cliente, no la factura.

### 15.4 Permisos en modo no interactivo

En una sesión de terminal, Claude Code pregunta antes de una acción que no está preaprobada. Con `-p` nadie puede contestar, así que lo que preguntaría se deniega y la fase muere a mitad. La solución adoptada es **reglas explícitas**, no un modo permisivo global:

- `.claude/settings.json` declara en `permissions.allow` exactamente lo que el orquestador necesita: invocar a los tres subagentes, ejecutar los verbos de `python -m app` y escribir en las carpetas de estado. Nada más.
- El frontend no puede dejar nada esperando una respuesta que no va a llegar. **El nombre exacto del argumento de la CLI que garantiza ese comportamiento no lo fija esta especificación**, y tampoco la sintaxis de las entradas de `permissions.allow` que autorizan a los subagentes: ambos se leen de la versión instalada (`claude --help` y la documentación de esa versión) antes de escribir el lanzador. Un argumento copiado de este documento sin verificar se ignora en silencio o cuelga la sesión, y las dos formas de fallar son peores que no tenerlo. Lo que sí fija esta especificación es la intención: modo no interactivo, sin preguntas pendientes, con permisos declarados uno a uno y sin modo permisivo global.
- Una regla que falte se manifiesta como una denegación que detiene la fase. No es un fallo silencioso: el registro de ejecución (§5.1) anota qué se denegó, y de ahí sale la regla que faltaba.

Se elige esto y no un modo amplio como `acceptEdits` por coherencia con §13.1 y §13.3: el proyecto entero está construido sobre dar el permiso mínimo y hacerlo cumplir con hooks. Un permiso amplio en el arranque anularía esa decisión desde fuera.

### 15.5 Límite aceptado

La pantalla escucha sin autenticación en `127.0.0.1` y ahora puede lanzar procesos que gastan dinero. El límite de confianza es la máquina: cualquier proceso local podría llamar a sus endpoints. Se acepta porque es el mismo límite que tiene la terminal, donde cualquier proceso local puede ejecutar `claude` igual. No se abre a la red, y por eso no se añade autenticación: añadirla daría una sensación de seguridad que el diseño no sostiene.

### 15.6 Fuera de alcance de esta versión

Resolver un reporte de QA desde la pantalla (RF-UI-04 lo excluye a propósito), leer capítulos en el navegador, editar la escaleta y lanzar tandas programadas. La resolución de QA es el caso más delicado del sistema y su protocolo de tres pasos (§8.2) exige editar archivos a mano entre el primero y el segundo; llevarlo a un botón antes de haberlo ejercitado a mano sería adelantarse.

## 16. Observabilidad de la ejecución (Langfuse)

### 16.1 Dónde se instrumenta y por qué ahí

La traza **no se emite durante la tanda**. Se exporta después, leyendo `07_registro/<tanda>/` (§5.1), con un verbo del CLI:

```
python -m app exportar-traza <tanda> [--con-cuerpos]
```

Dos razones, y las dos son de diseño, no de comodidad:

- Un hook está en el camino crítico. Si emitiera por red, un servicio lento o caído frenaría o rompería una tanda que cuesta dinero de verdad. **La observabilidad no puede tumbar lo observado.**
- Exportar desde el registro es reejecutable. Una tanda vieja se vuelve a subir cuando cambia el mapeo, y una tanda que falló a mitad se sube igual, que es justo cuando más falta hace verla.

El registro sigue siendo la fuente de verdad. Langfuse es una vista de él, no el original: si el servicio desaparece, no se pierde nada auditable.

### 16.2 Mapeo del registro a la traza

| Objeto en Langfuse | Qué es aquí | Campos |
|---|---|---|
| `trace` | una tanda | nombre `tanda_<ts>`; metadata: `total_capitulos`, `capitulos_por_tanda`, `cadencia_qa`, los tres `prompts_hash` del manifiesto y la versión de estas especificaciones |
| `span` | un capítulo | nombre `cap_N`; abarca escritor, extractor y, si toca corte, QA |
| `generation` | una invocación de subagente | nombre `<rol>:cap_N`; `model`; `usage` (§16.3); entrada y salida solo con `--con-cuerpos` |
| `event` | un bloqueo de hook, un fallo de autovalidación (EX-10) o un descarte de borrador (EX-08) | el `id` del hook y su motivo textual |
| `score` | las métricas de un corte de QA y de la tanda | §16.4 |

Los `prompts_hash` en la metadata no son decoración: sin ellos, comparar dos tandas no dice nada, porque no se sabe si corrieron con el mismo prompt.

### 16.3 El consumo hay que mapearlo completo

`uso.jsonl` trae cuatro cifras de tokens y **las cuatro tienen que viajar**: `tokens_entrada`, `tokens_salida`, `tokens_cache_lectura` y `tokens_cache_creacion`.

Mapear solo entrada y salida produce trazas activamente engañosas. En la corrida de prueba, una invocación real del escritor registró 6 tokens de entrada y 42 129 de lectura de caché: casi toda la entrada real está en la caché. Una traza que solo mire `tokens_entrada` dirá que el capítulo costó seis tokens, y el panel de costes dirá cero. Es peor que no tener panel, porque un número falso se cree.

El límite que esto conserva: estas cifras las lee H-10 del transcript del subagente. Son contabilidad del cliente, no la factura del proveedor. Sirven para comparar tandas entre sí, no para conciliar gasto.

### 16.4 Puntuaciones

Es la única parte que convierte a Langfuse en algo más que un log bonito. Sin puntuaciones no se puede responder a la única pregunta que importa: *¿este cambio mejoró la novela o solo la cambió?*

| Puntuación | Tipo | De dónde sale |
|---|---|---|
| `qa_contradicciones` | numérica | hallazgos de tipo `contradiccion` del reporte del corte |
| `qa_repeticiones` | numérica | hallazgos de tipo `repeticion` |
| `qa_pasa` | booleana | negación de `tiene_contradicciones` |
| `desvio_longitud` | numérica | el mayor desvío relativo respecto a `palabras_por_capitulo` entre los capítulos de la tanda |
| `borradores_descartados` | numérica | descartes por EX-08 en la tanda |

### 16.5 Identidad e idempotencia

El `agent_id` que trae el payload del hook es lo que une `eventos.jsonl` con `uso.jsonl`, y es el identificador de la `generation`. La tanda identifica la traza. Con eso, **reexportar la misma tanda no duplica nada**: se actualiza lo que ya está. Es un requisito, no una propiedad deseable, porque el exportador se va a correr varias veces sobre la misma tanda mientras se afina el mapeo.

### 16.6 Qué sale de la máquina y qué no

Por defecto salen estructura, tiempos, modelos, tokens, conteos y puntuaciones. **No sale prosa ni el cuerpo de ningún prompt.**

`--con-cuerpos` los incluye, y existe porque depurar un prompt sin poder verlo es imposible. Es opt-in por una razón concreta: `prompts/` contiene la guía de estilo destilada de `00_referencias/`, que está fuera del control de versiones porque pueden ser obras publicadas (RF-00.2). Lo que se decidió no versionar tampoco se sube a un servicio de terceros por descuido.

### 16.7 Credenciales

Las variables de Langfuse se leen del entorno, igual que la de OpenRouter (§3.1), y **nunca** de `config/`, de `.claude/settings.json` ni de los tests. Si faltan, `exportar-traza` falla con el motivo y no hace nada más. No puede romper una tanda porque no corre dentro de ninguna.

### 16.8 Sin verificar contra la versión instalada

Esta sección **no fija los nombres del SDK ni de sus parámetros**, por la misma razón que §15.4 no fija los argumentos de la CLI. Antes de escribir el exportador hay que comprobar dos cosas contra la versión instalada de la biblioteca:

1. Si permite fijar explícitamente los instantes de inicio y fin de cada observación. El exportador publica hechos pasados: si la biblioteca solo sabe marcar «ahora», todas las trazas saldrán apiladas en el instante de la exportación y las duraciones serán falsas.
2. Si su modelo de consumo admite las cuatro cifras de §16.3, caché incluida.

Si alguna de las dos no se cumple, la alternativa es la API de ingesta por HTTP, que acepta ambos y no añade dependencia. La decisión se toma con el `--help` y la documentación delante, no con este documento.

## 17. Antirrepetición de prosa

El corte de QA de la corrida de prueba devolvió dos contradicciones y **ocho repeticiones**, entre ellas una frase literal idéntica en tres capítulos. No es un fallo del prompt: es una consecuencia directa de INV-01. El escritor no lee el manuscrito, así que **no tiene forma de saber que ya usó una imagen**. El resumen rodante lleva trama, no tics de prosa.

La solución no puede ser dejarle leer capítulos anteriores: eso destruye el invariante que sostiene el coste y la escalabilidad del sistema. Son dos capas, ninguna de las cuales le da acceso al manuscrito.

### 17.1 Capa determinista: `validar-capitulo`

`validar-capitulo N` (§8.2) añade una comprobación: ninguna secuencia de cuatro o más palabras con contenido léxico puede aparecer literalmente en un capítulo anterior. Las secuencias formadas solo por palabras vacías se ignoran, o el validador saltaría en cada «en el interior de la».

Esto lo hace un script, que lee todo el manuscrito sin violar nada: INV-01 restringe al **agente** escritor, no al código determinista. Es barato, no llama a ningún modelo y atrapa con certeza el caso literal («el metal estaba frío», tres capítulos). Si falla, el escritor reescribe dentro de su propio bucle de autovalidación (RF-08.4).

### 17.2 Capa semántica: el extractor ya está leyendo

Las repeticiones estructurales no son literales: una cadencia sintáctica, un gesto, una muletilla de un personaje. Un validador de n-gramas no las ve.

El extractor sí las ve, porque lee el capítulo entero y ya está pagado. Su delta (§4) gana un campo `recursos_narrativos`: las imágenes, gestos y giros recurrentes que detecta, con su conteo acumulado. Se acumulan en el estado como los hechos de continuidad, y `preparar-capitulo` inyecta los más usados en el prompt del escritor como una lista de **recursos agotados**, no como prohibición absoluta: una imagen recurrente puede ser deliberada, y el objetivo es que el escritor sepa que la está repitiendo, no que no pueda hacerlo nunca.

El coste marginal es de unos cientos de tokens por capítulo y no añade ninguna invocación de modelo.

### 17.3 Lo que esto toca

El esquema de `Delta` en §4 (campo nuevo), `preparar-capitulo` y `validar-capitulo` en §8.2, y el prompt del escritor en §13.1. El tope de `max_hechos_por_capitulo` no aplica a `recursos_narrativos`: son listas distintas con crecimientos distintos, y meterlas en el mismo tope haría que los tics desplazaran a los hechos de continuidad, que es exactamente al revés de lo que interesa.
