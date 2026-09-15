# Especificación Técnica — Harness Generador de Novelas de Terror

**Versión:** 1.0
**Documento base:** `especificacion-funcional-harness-novela-terror.md` v1.0 — todo lo que sigue implementa esos requisitos (RF-XX) sin redefinir su comportamiento.
**Lector previsto:** el agente de código que implementa el harness. Toda decisión no cubierta aquí y no derivable de la especificación funcional debe tratarse como pregunta abierta, no como espacio para asumir.

## 1. Decisiones de arquitectura declaradas

Decisiones tomadas para poder avanzar, con su razón — si alguna deja de aplicar, hay que revisar en cascada lo que depende de ella.

| Decisión | Razón |
|---|---|
| Runtime: **Python 3.11+** | Ecosistema maduro para orquestación de agentes, validación de esquemas y scripts de larga duración. |
| Acceso a LLM vía **adapter intercambiable**, empezando por OpenRouter | La cuenta de Claude Code no es reutilizable como API para automatización. OpenRouter permite arrancar en capa gratuita y migrar a un proveedor de pago (Anthropic directo u otro modelo en OpenRouter) sin rediseñar el harness. |
| **Modelos distintos por rol** | El agente escritor depende de calidad de prosa (modelo más capaz); extractor y QA son tareas estructuradas (JSON, comparación de hechos) que toleran un modelo más barato/rápido. |
| **Esquemas formales con Pydantic** | Valida cada artefacto de estado antes de persistirlo; permite rechazar y reintentar cuando el LLM produce JSON inválido (EX-01). |
| **Checkpointing/reanudación** | Los artefactos ya se persisten en disco por capítulo (ver `harness-novela-terror.md`); el harness debe poder detectar dónde quedó una tanda interrumpida y continuar sin repetir capítulos cerrados. |

## 2. Arquitectura de módulos

```
harness/
├── config.py                 # carga y valida harness.config.json
├── schemas/
│   ├── personajes.py          # Personaje, FichaPersonajes
│   ├── continuidad.py         # HechoContinuidad, LogContinuidad
│   ├── outline.py             # EntradaOutline, Outline
│   ├── qa.py                  # Hallazgo, ReporteQA
│   └── deltas.py               # DeltaExtraccion
├── llm/
│   ├── base.py                # interfaz LLMProvider (abstracta)
│   ├── openrouter.py           # implementación OpenRouter
│   ├── anthropic_directo.py    # implementación futura, mismo contrato
│   └── roles.py                 # mapa rol → (provider, modelo), leído de config
├── agents/
│   ├── escritor.py             # RF-05.1, RF-05.2
│   ├── extractor.py            # RF-06.1
│   └── qa.py                   # RF-07.1, RF-07.2, RF-07.3
├── state/
│   ├── repository.py           # lectura/escritura con validación (EX-01)
│   ├── continuidad.py          # aplicar deltas, append-only (RF-06.3, INV-03)
│   ├── personajes.py           # aplicar deltas (RF-06.2)
│   └── resumen_rodante.py      # ventana deslizante (RF-06.4)
├── orchestrator/
│   ├── loop.py                 # loop principal fases 5-7
│   └── checkpoint.py           # detecta último capítulo cerrado, permite reanudar
└── cli.py                      # punto de entrada: `python -m harness run`
```

Regla de dependencia que el agente implementador debe respetar: `agents/escritor.py` **no importa** `state.repository.leer_manuscrito` bajo ninguna firma — es la forma de hacer cumplir INV-01 (el escritor nunca lee capítulos cerrados) a nivel de código, no solo de prompt.

## 3. Capa de acceso a LLM

### 3.1 Interfaz (`llm/base.py`)

```python
class LLMProvider(ABC):
    @abstractmethod
    def generate(self, *, system: str, prompt: str, model: str,
                 max_tokens: int, temperature: float = 0.7) -> str:
        """Devuelve el texto generado. Lanza RateLimitError o ProviderError."""

class RateLimitError(Exception): ...
class ProviderError(Exception): ...
```

Todo agente (`escritor.py`, `extractor.py`, `qa.py`) depende de `LLMProvider`, nunca de un cliente HTTP concreto — así cambiar de OpenRouter a Anthropic directo es un cambio de configuración, no de código.

### 3.2 Selección de modelo por rol (`llm/roles.py`)

Se resuelve desde `harness.config.json` (sección `proveedores`), no está hardcodeado:

```json
"proveedores": {
  "escritor":  { "provider": "openrouter", "model": "<MODELO_CAPAZ>" },
  "extractor": { "provider": "openrouter", "model": "<MODELO_ECONOMICO>" },
  "qa":        { "provider": "openrouter", "model": "<MODELO_ECONOMICO>" }
}
```

### 3.3 Política de reintentos

Dado que la capa gratuita de OpenRouter tiene rate limits agresivos, todo llamado LLM pasa por una política de reintento con backoff exponencial:

| Tipo de fallo | Reintentos | Backoff | Acción tras agotar reintentos |
|---|---|---|---|
| `RateLimitError` | hasta `reintentos.max_intentos` (config) | `backoff_base_segundos * 2^intento` | Aborta el capítulo actual, deja checkpoint en el capítulo previo (no avanza). |
| JSON inválido del extractor/QA | hasta `reintentos.max_intentos`, reenviando el error de validación al modelo como corrección | fijo, 1s | Aborta y dispara EX-01. |
| `ProviderError` (5xx, timeout) | hasta `reintentos.max_intentos` | igual que RateLimitError | Aborta y reporta al usuario, sin marcar el capítulo como cerrado. |

### 3.4 Conteo de tokens para RF-05.1

El criterio de aceptación de RF-05.1 exige no exceder `max_tokens_contexto_escritor`. Como el conteo exacto depende del tokenizador de cada proveedor, se usa una estimación (`tiktoken` como aproximación conservadora, +15% de margen) — se documenta como aproximación, no como conteo exacto, para no dar falsa precisión.

## 4. Esquemas de datos (Pydantic)

Corresponden 1:1 a los esquemas descritos en `harness-novela-terror.md` §3, ahora como contrato validable.

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
    hecho: str
    cap_origen: int

class LogContinuidad(RootModel[list[HechoContinuidad]]): ...

# schemas/outline.py
class EntradaOutline(BaseModel):
    num: int
    objetivo_narrativo: str
    personajes: list[str]
    locacion: str
    informacion_nueva: str
    tension: int = Field(ge=1, le=5)

# schemas/deltas.py
class DeltaExtraccion(BaseModel):
    personajes: dict[str, Personaje]   # solo los que cambiaron
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

## 5. Artefacto técnico adicional: manifiesto de ejecución

No forma parte de la especificación funcional (es puramente de soporte técnico para checkpointing). Vive en `04_estado/manifest.json`:

```json
{
  "ultimo_capitulo_cerrado": 12,
  "ultimo_qa_ejecutado": 8,
  "total_capitulos_esperado": 40,
  "estado": "en_progreso"   // en_progreso | pausado_por_qa | completo
}
```

`orchestrator/checkpoint.py` lee este archivo al iniciar; si `estado == "pausado_por_qa"`, el harness no reanuda automáticamente (implementa RF-07.4) hasta que el usuario marque el reporte correspondiente como resuelto.

`total_capitulos_esperado` guarda el valor con el que se generó la escaleta. Al reanudar se compara contra `config.total_capitulos`; si difieren y `ultimo_capitulo_cerrado > 0`, se dispara EX-06.

El manifiesto **no** registra nada sobre la tanda en curso (ni el tope ni cuántos capítulos lleva). El conteo de `capitulos_por_tanda` vive solo en memoria durante la ejecución: es un límite de esta corrida, no un hecho de la novela. Persistirlo daría a entender que la partición en tandas es parte del estado de la obra, y por INV-06 no lo es.

## 6. Orquestador — mapeo del loop a módulos

Pseudocódigo de `orchestrator/loop.py`, con cada paso anotado al requisito funcional que implementa:

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
```

Ninguna de estas se captura silenciosamente en `orchestrator/loop.py`: todas terminan la ejecución de la tanda y dejan el `manifest.json` en un estado consistente con lo que sí se alcanzó a cerrar.

## 8. Configuración extendida (`harness.config.json`)

```json
{
  "total_capitulos": 40,
  "capitulos_por_tanda": 5,
  "palabras_por_capitulo": 3000,
  "ventana_resumen_rodante": 3,
  "cadencia_qa": 8,
  "max_tokens_contexto_escritor": 5000,
  "proveedores": {
    "escritor":  { "provider": "openrouter", "model": "<MODELO_CAPAZ>" },
    "extractor": { "provider": "openrouter", "model": "<MODELO_ECONOMICO>" },
    "qa":        { "provider": "openrouter", "model": "<MODELO_ECONOMICO>" }
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
    palabras_por_capitulo: int = Field(gt=0)          # RF-CFG-01
    ventana_resumen_rodante: int = Field(ge=1)
    cadencia_qa: int = Field(ge=1)
    max_tokens_contexto_escritor: int = Field(gt=0)
```

`capitulos_por_tanda` **no** se valida contra `total_capitulos`: un tope mayor que los capítulos restantes es válido y simplemente significa "terminá la novela" (RF-CFG-02).

Al reanudar, `checkpoint.py` compara `config.total_capitulos` contra la cantidad de entradas de `capitulos.json`. Si difieren y ya hay capítulos cerrados, dispara `ConfiguracionInconsistenteError` (EX-06) en vez de reanudar — cambiar el tamaño de la obra a mitad de camino invalida la escaleta.

### 8.2 Interfaz de línea de comandos

```bash
python -m harness run                    # usa capitulos_por_tanda del archivo
python -m harness run --capitulos 3      # pisa el valor del archivo (RF-CFG-03)
python -m harness run --hasta-el-final   # ignora el tope y sigue hasta total_capitulos
python -m harness status                 # imprime el manifiesto sin generar nada
```

Solo `capitulos_por_tanda` admite override. `total_capitulos` y `palabras_por_capitulo` no se exponen como argumentos a propósito: pasarlos por línea de comandos invitaría a cambiarlos entre tandas, que es justo lo que EX-06 e INV-04 buscan impedir.

## 9. Plan de pruebas

| Nivel | Qué cubre | Cómo |
|---|---|---|
| Unitarias | Cada criterio de aceptación de la especificación funcional que sea verificable sin LLM real (validación de esquemas, append-only de continuidad, recorte de resumen rodante, cálculo de reanudación). | `pytest`, sin llamadas externas. |
| Integración con LLM simulado | El loop completo de `ejecutar_tanda` para 3 capítulos, con un `LLMProvider` de prueba que devuelve respuestas fijas. | Verifica que `agents/escritor.py` nunca reciba una ruta de `05_manuscrito/`, y que el manifiesto quede consistente tras una interrupción simulada a mitad de tanda. |
| Manual, con LLM real | Corrida de 8-10 capítulos reales antes de comprometerse a una tanda completa, revisando `personajes.json` y `continuidad.json` a mano. | Igual que el checklist de `harness-novela-terror.md` §7. |
| Equivalencia de tandas (INV-06) | Que partir la generación en tandas no cambie el resultado. | Con `LLMProvider` determinista: correr 6 capítulos de una vez y, en otro directorio, correr 3 + 3. Los artefactos de estado y los `cap_*.md` deben ser idénticos byte a byte. |
| Reanudación (RF-CFG-04, INV-07) | Que reanudar avance y nunca reescriba. | Correr una tanda de 3, anotar los `mtime` de `cap_1..3.md`, correr otra tanda de 3, verificar que esos `mtime` no cambiaron y que aparecieron `cap_4..6.md`. |

## 10. Trazabilidad requisito → componente técnico

| Requisito funcional | Componente técnico |
|---|---|
| RF-05.1 (ensamblado de contexto) | `agents/escritor.py::ensamblar_contexto`, `llm/roles.py` |
| RF-05.3 (restricción de acceso del escritor) | Regla de dependencias §2 — `escritor.py` no importa lectura de manuscrito |
| RF-06.1 (extracción de un solo capítulo) | `agents/extractor.py::extraer` — firma solo acepta `cap_n: str`, no una lista |
| RF-06.3 (continuidad append-only) | `state/continuidad.py::aplicar_delta` — solo expone `agregar()`, sin `eliminar()` ni `modificar()` |
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
