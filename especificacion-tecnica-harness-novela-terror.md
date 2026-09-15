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
│   ├── continuidad.py          # append-only, filtrado por relevancia (RF-06.3, RF-05.1, INV-03)
│   ├── personajes.py           # aplicar deltas, registro de sujetos (RF-06.2, RF-06.1)
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

## 8. Configuración extendida (`config/`)

La configuración vive en una **carpeta**, no en un único archivo. El inventario completo y la razón de la partición están en §11; lo que sigue es el contenido consolidado, como referencia rápida de todos los parámetros juntos.

```json
{
  "total_capitulos": 40,
  "capitulos_por_tanda": 5,
  "max_llamadas_por_tanda": null,
  "registrar_uso": true,
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
    max_llamadas_por_tanda: int | None = Field(default=None, ge=1)  # RF-CFG-06
    registrar_uso: bool = True                        # RF-CFG-06
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
| **Calidad de atribución de sujeto** (RF-06.1) | Que el filtrado de RF-05.1 se apoye en datos confiables. **Es el criterio que decide si el diseño de §12.3 se sostiene.** | Sobre los 8-10 capítulos de la corrida manual: revisar a mano cada hecho de `continuidad.json` y contar cuántos tienen el `sujeto` correcto. Medir también la proporción de `sujeto_validado = false`. |
| Cobertura del filtro (RF-05.1) | Que filtrar no omita hechos relevantes. | Para cada capítulo de la corrida manual, comparar los hechos inyectados contra el log completo y revisar si algún hecho excluido era pertinente a lo que el capítulo terminó narrando. |

Criterio de decisión para las dos filas nuevas: si la atribución de sujeto acierta por debajo de ~90%, o si aparece algún hecho pertinente excluido por el filtro, hay que volver a inyectar `continuidad.json` completo y asumir el costo de contexto. El resto del esquema (`sujeto`, `categoria`, `superado_por`) se conserva igual: sigue sirviendo para QA y para RF-07.6 aunque el escritor no filtre.

## 10. Trazabilidad requisito → componente técnico

| Requisito funcional | Componente técnico |
|---|---|
| RF-05.1 (ensamblado de contexto) | `agents/escritor.py::ensamblar_contexto`, `llm/roles.py` |
| RF-05.3 (restricción de acceso del escritor) | Regla de dependencias §2 — `escritor.py` no importa lectura de manuscrito |
| RF-06.1 (extracción de un solo capítulo) | `agents/extractor.py::extraer` — firma solo acepta `cap_n: str`, no una lista |
| RF-06.3 (continuidad append-only) | `state/continuidad.py::aplicar_delta` — solo expone `agregar()` y `marcar_superado()`, sin `eliminar()` ni `modificar()` |
| RF-05.1 (filtrado por relevancia) | `state/continuidad.py::filtrar_para_capitulo(entrada_outline)` — devuelve una selección de lectura; no escribe |
| RF-06.1 (registro de sujetos) | `state/personajes.py::sujetos_conocidos()` + validador Pydantic sobre `HechoContinuidad.sujeto`; un sujeto fuera del registro fija `sujeto_validado = False`, no rechaza el hecho |
| RF-07.6 (reextracción tras corrección) | `state/continuidad.py::marcar_superado(caps)` — fija `superado_por`, nunca borra (INV-03) |
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

### 11.4 `proveedores.json`

| Parámetro | Nota |
|---|---|
| `escritor.provider` / `.model` / `.temperature` | Modelo capaz. La temperatura del escritor es el único parámetro de muestreo que importa para la prosa |
| `extractor.provider` / `.model` / `.temperature` | Modelo económico. Temperatura baja: la tarea es estructurada |
| `qa.provider` / `.model` / `.temperature` | **Ver §11.7**: la asignación de modelo económico a QA está en discusión |
| `reintentos.max_intentos` / `.backoff_base_segundos` | §3.3 |

Las claves de API se leen siempre de variables de entorno, nunca de estos archivos.

### 11.5 `config/prompts/` — los prompts son artefactos versionados

Los prompts de los tres agentes viven en archivos, no embebidos en el código Python. Razón: son lo que más se itera, y si están en el código cada ajuste de redacción es un commit de código con diff ilegible. En archivos, el diff muestra exactamente qué instrucción cambió entre una tanda y la siguiente.

El manifiesto registra el hash del prompt usado por cada rol al iniciar la tanda. Si un capítulo sale mal, se puede saber con qué versión del prompt se generó.

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
| Modelo del agente QA | La spec asigna modelo económico. Pero QA cruza ~34.000 tokens de prosa contra ~150 hechos: es razonamiento sobre contexto largo, justo donde los modelos económicos flojean. Corre 5 veces contra las 40 del escritor, así que moverlo al modelo capaz cuesta poco. **Pendiente de decidir.** |
| `mundo.json` | **Resuelto por §12.3.** Sus locaciones alimentan el registro de sujetos de RF-06.1 y la clave de filtrado de RF-05.1, así que ya no es un artefacto huérfano. Su *contenido* sigue sin inyectarse al escritor, y es correcto: las reglas del universo que deben condicionar la escritura viven como hechos de `categoria = "mundo"` en `continuidad.json` (RF-04.3), que sí se inyectan siempre. `mundo.json` queda como registro de locaciones y referencia humana. |
| Selección entre borradores | Fuera de alcance por decisión explícita (§2 de la spec funcional). Es la diferencia principal contra Re3, que genera varias continuaciones y rerankea por coherencia. Conviene dejar registrado que es una limitación conocida, no un olvido. |

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

## 13. Ruta alternativa de implementación: Claude Code

La §1 decidió harness propio en Python contra API, con la razón de que una cuenta de Claude Code no es reutilizable como API para automatización. La razón sigue siendo válida para la tanda completa desatendida. Pero para las corridas de validación que pide §9 (8–10 capítulos revisados a mano), Claude Code cubre el pipeline sin escribir el harness, y con una ventaja concreta: **algunos invariantes dejan de depender del prompt y pasan a ser configuración declarativa.**

### 13.1 Mapeo de los tres agentes a subagentes

Un subagente de Claude Code se define en `.claude/agents/<nombre>.md`, con frontmatter YAML y el system prompt en el cuerpo. Arranca con contexto aislado: no ve la conversación principal ni los archivos que ya se leyeron.

Los campos que interesan acá son `tools` (allowlist) y `disallowedTools` (denylist). Con ellos, INV-01 e INV-05 se vuelven configuración:

```markdown
---
name: escritor
description: Redacta el borrador de un capítulo a partir del estado persistente
model: opus
tools: Read, Write
disallowedTools: Grep, Glob, Bash, WebFetch
memory: project
---
```

El aislamiento de contexto del subagente da INV-02 casi gratis: el extractor solo ve el prompt que se le pasa, así que no puede acceder a capítulos anteriores aunque quisiera.

Correspondencia con los invariantes:

| Invariante | En el harness Python | En Claude Code |
|---|---|---|
| INV-01 (escritor sin manuscrito) | `escritor.py` no importa `leer_manuscrito` | `tools` sin herramientas de búsqueda, y el orquestador controla qué rutas pasa |
| INV-02 (extractor, un capítulo) | Firma `extraer(cap_n: str)` | Aislamiento de contexto del subagente |
| INV-05 (solo QA lee varios) | Solo `qa.py` importa `leer_muestra_manuscrito` | Solo el subagente `qa` lleva `Grep`/`Glob` en su allowlist |

Honestidad sobre el alcance: ni `tools` ni el aislamiento restringen **qué rutas** puede leer un agente que sí tiene `Read`. La garantía real de INV-01 sigue estando en que el orquestador no le pase rutas de `05_manuscrito/`. Es más fuerte que solo prompt, menos fuerte que la regla de importación de §2.

### 13.2 Fases como skills

Cada fase del pipeline es una skill en `.claude/skills/<nombre>/SKILL.md`. Las skills admiten `context: fork` para correr en subagente, `allowed-tools` para preaprobar herramientas, y sustitución de la salida de un comando en el prompt antes de que el modelo lo vea — útil para cargar el estado sin que el modelo tenga que ir a buscarlo.

```
.claude/skills/
├── destilar-estilo/SKILL.md     # fase 0
├── generar-premisa/SKILL.md     # fase 1
├── generar-sinopsis/SKILL.md    # fase 2
├── generar-escaleta/SKILL.md    # fase 3
├── inicializar-estado/SKILL.md  # fase 4
├── escribir-capitulo/SKILL.md   # fases 5-6, invoca los subagentes
└── corte-qa/SKILL.md            # fase 7
```

Las que tienen efectos irreversibles (escribir un capítulo, cerrar un corte) llevan `disable-model-invocation: true`, para que solo las dispare el usuario y no el modelo por su cuenta.

### 13.3 Hooks para las validaciones

Un hook `PostToolUse` con matcher `Write` puede validar el JSON contra su esquema apenas se escribe, que es exactamente EX-01. A diferencia de la validación dentro del harness, esto corre aunque el agente escriba el archivo por un camino no previsto.

```json
{
  "hooks": {
    "PostToolUse": [
      { "matcher": "Write",
        "hooks": [{ "type": "command", "command": "scripts/validar-estado.py" }] }
    ]
  }
}
```

### 13.4 Empaquetado como plugin

Un plugin agrupa skills, agentes, hooks y servidores MCP en un directorio con manifiesto `.claude-plugin/plugin.json`. Si el flujo se estabiliza, empaquetarlo lo hace instalable y versionable:

```
novela-harness/
├── .claude-plugin/plugin.json
├── skills/          # las 7 fases
├── agents/          # escritor, extractor, qa
└── hooks/hooks.json # validación de esquemas
```

### 13.5 CLAUDE.md como reglas ambientales

`CLAUDE.md` se carga al inicio de cada sesión, incluida la de cada subagente. Es el lugar para los invariantes que deben regir siempre: nunca pasar rutas de `05_manuscrito/` al escritor, nunca borrar hechos de `continuidad.json`, siempre validar antes de persistir.

No sustituye a las restricciones de `tools` — es la capa de intención, no la de cumplimiento.

### 13.6 Qué sigue faltando por esta ruta

Sigue sin cubrirse lo que §1 ya anticipaba: ejecución desatendida de una tanda larga, política de reintentos con backoff, determinismo entre corridas, y auditoría automática de qué archivos leyó cada agente (RF-05.3). Para la novela completa, el harness en Python sigue siendo la respuesta.

## 14. Referencias

Trabajos consultados al dimensionar la memoria y el control de continuidad:

- **DOME** — memoria de largo plazo como grafo temporal de cuádruplas, detección de conflictos por reglas, métricas Ent-2 y tasa de conflicto. <https://arxiv.org/html/2412.13575>
- **Re3** — plan, generación, reranking de continuaciones y edición por consistencia factual. Origen del patrón "plan + estado inyectado" que usa este harness. <https://arxiv.org/abs/2210.06774>
- **DOC** — control detallado del outline y desarrollo de personajes a lo largo del tiempo. <https://aclanthology.org/2023.acl-long.190.pdf>
- **Subagentes de Claude Code** — aislamiento de contexto y restricción declarativa de herramientas. <https://code.claude.com/docs/en/sub-agents>
- **Skills de Claude Code** — carga progresiva, `context: fork`, scripts embebidos. <https://code.claude.com/docs/en/skills>
- **Plugins de Claude Code** — empaquetado de skills, agentes y hooks. <https://code.claude.com/docs/en/plugins>
