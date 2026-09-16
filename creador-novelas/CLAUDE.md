# creador-novelas: harness de novelas de terror espacial

Pipeline de 8 fases que escribe una novela capítulo a capítulo sin que el manuscrito acumulado vuelva al contexto de generación. Tres subagentes (escritor, extractor, qa) hacen la generación; scripts Python deterministas (`app/`) validan, filtran, persisten y llevan el manifiesto; los hooks hacen cumplir los invariantes. Especificaciones en la raíz del repo: `../especificacion-funcional-harness-novela-terror.md` y `../especificacion-tecnica-harness-novela-terror.md` (v1.4). Todas las rutas de las specs son relativas a esta carpeta.
**Regla de las specs:** donde haya ambigüedad, detenerse y preguntar al usuario; nunca asumir ni resolverla editando la spec.
Intérprete: siempre `.venv/Scripts/python.exe -m app <verbo>` (§8.2), nunca `python` a secas.

## Mapa de carpetas y quién toca cada una
- `01_concepto/`: `idea.md` (usuario o formulario) y `premisa.md` (fase 1). Solo vía `guardar`.
- `00_referencias/`: ejemplos del subgénero, fuera de git; solo la fase 0 los lee.
- `04_estado/`: style_guide, tres_actos, capitulos.json, personajes.json, mundo.json, continuidad.json (append-only), resumen_rodante.md, manifest.json, uso.jsonl. Solo los escribe el CLI. `prompts/` y `deltas/` son artefactos de trabajo.
- `05_manuscrito/cap_N.md`: solo el escritor escribe el capítulo activo; solo QA lee varios; el orquestador no lo abre.
- `06_qa/`: reportes `qa_cap_N.md` + `.json` y `recursos_usados.json`; solo QA escribe aquí.
- `config/`: novela.json (inmutable con capítulos cerrados), ejecucion.json, proveedores.json, prompts/ por rol.
- `.claude/agents/`: escritor.md, extractor.md, qa.md. `.claude/skills/`: fases y skills de dominio. `scripts/hooks/`: H-01 a H-10.
- `.tanda/`: cursor transitorio de la tanda y estado de hooks; no es estado de la novela.

## Orden de fases (skill que la dispara → condición de entrada → artefacto)
1. `/destilar-estilo` → `00_referencias/` con textos → `04_estado/style_guide.md`
2. `/generar-premisa` → `01_concepto/idea.md` → `01_concepto/premisa.md`
3. `/generar-sinopsis` → premisa.md → `04_estado/tres_actos.md`
4. `/generar-escaleta` → tres_actos.md + config/novela.json → `04_estado/capitulos.json` (crea manifest.json)
5. `/inicializar-estado` → capitulos.json + tres_actos.md → personajes.json, mundo.json, continuidad.json
6. `/escribir-tanda [N|--hasta-el-final]` → los cinco anteriores → cap_N.md por capítulo, estado actualizado, QA cada `cadencia_qa`
7. `/corte-qa` → capítulos cerrados → reporte en `06_qa/reportes/`
8. `/resolver-qa` → manifiesto con `reextraccion_pendiente` (tras `resolver --capitulos`) → estado reextraído
La entrada se prepara con `python -m app ui` (formulario local) o editando `01_concepto/idea.md` y `config/`.

## Reglas del orquestador (esta sesión)
- INV-08: nunca leer `05_manuscrito/`, nunca escribir prosa, nunca editar un artefacto de estado a mano. Solo skills, subagentes y CLI.
- INV-09: un solo nivel de delegación: esta sesión invoca escritor, extractor y qa; ningún agente lanza otro.
- Nunca pasar rutas de `05_manuscrito/` al escritor: su contexto es el archivo `04_estado/prompts/escritor_cap_N.md` que produce `preparar-capitulo`.
- Todo cambio de estado pasa por el CLI (`guardar`, `aplicar-delta`, `cerrar-qa`, `resolver`); el JSON del extractor se deja en `04_estado/deltas/delta_cap_N.json` y lo aplica `aplicar-delta`.
- Para leer lo generado: `python -m app ensamblar --salida <archivo>`, y se le muestra la ruta al usuario.

## Invariantes
- INV-01: el escritor nunca recibe el texto de un capítulo cerrado (sin Read; H-06).
- INV-02: el extractor nunca recibe más de un capítulo por invocación (H-05).
- INV-03: todo hecho de continuidad.json lleva `cap_origen`; el log es append-only, solo se marca `superado_por` (H-03).
- INV-04: esquemas y `config/novela.json` no cambian con capítulos cerrados (H-04, EX-06).
- INV-05: solo QA lee varios capítulos a la vez (allowlist + H-06).
- INV-06: `capitulos_por_tanda` no altera ningún artefacto: el conteo vive en `.tanda/cursor.json`.
- INV-07: ningún capítulo cerrado se regenera; reanudar siempre avanza desde `ultimo_capitulo_cerrado + 1`.

## Contratos de retorno (RF-08.1) y qué hacer si no se cumplen
- escritor → una línea `cap_N.md · <palabras> palabras · personajes: A, B`; nunca prosa. Se valida con `registrar-escritor N "<línea>"`.
- extractor → solo el JSON del DeltaExtraccion. Se guarda en `04_estado/deltas/delta_cap_N.json` y se valida con `aplicar-delta N`.
- qa → hasta cinco líneas con `tiene_contradicciones` y conteos; el detalle queda en `06_qa/reportes/`. Se cierra con `cerrar-qa N`.
- Si un retorno no cumple su forma: no reintentar por otra vía ni completar a mano; reenviar al mismo agente el error textual del CLI una vez, y si repite, detenerse y reportarlo al usuario.
- Si un hook bloquea algo: no rodearlo. Anotar qué bloqueó y a quién, y reportarlo.
