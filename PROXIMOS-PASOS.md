# Qué probar ahora, y qué está descartado

Estado al 19/09/2026. Sale de las 20 novelas medidas (ver `HALLAZGOS.md`) y de una investigación
sobre el estado del arte del 19/09.

## Descartado, con el motivo

**Sustituir el orquestador LLM por un bucle de Python.** Era la sospecha principal: está presente
16–20 de los 20 minutos de una novela. **Medido: 0,8 min, el 8 % de la tanda.** El 92 % del tiempo
hay algún agente trabajando; su «presencia» es espera, no decisión. Sustituirlo daría medio minuto
sobre veinte.

**Ejecución especulativa de pasos.** El propio trabajo que la propone (PASTE, 2026, −48,5 % de
latencia) acota que solo paga cuando las llamadas a herramientas dominan el tiempo, 35–61 %. Nuestro
camino crítico es generación de Opus.

**Gestión sofisticada de KV-cache** (CacheScout, SpecBox). Optimizan huecos que aquí ya están
solapados, y lo solapado ya es gratis.

**Volver a QA por lotes.** Medido: +21 % de reloj y 3 contradicciones por novela. *Sherlock* (2025)
apunta en la misma dirección: el diseño óptimo publicado es verificar incremental y solapado.

**Quitar el extractor.** Medido: quita 7,4 min de trabajo y 0,4 de reloj, y sube las contradicciones.

**Añadir más agentes especializados.** Anthropic mide 3–10× tokens en sistemas multiagente y «a
menudo más tiempo total».

**Montar un grafo de eventos.** 138 hechos ≈ 5.400 tokens caben cuatro veces en el presupuesto del
escritor. Ver Spec-X 05: lo que falta son aristas, no un motor de consulta.

## Por probar, en orden

### 1. Caché de prefijos en el escritor y en QA

**La única palanca que queda sobre el camino crítico**, y es reordenar cadenas, no arquitectura.

La caché de Anthropic casa **por prefijo, byte a byte**. Si el prompt se arma con el estado en orden
variable --el filtro cambia de capítulo a capítulo, el JSON no sale ordenado--, cada capítulo es un
fallo de caché completo y se vuelve a pagar el prefill entero de un prompt de ~12.000 tokens, en
Opus, tres veces por novela y otras tantas en QA.

Reordenar el prompt como **[guía de estilo + sinopsis + canon del preludio]** (inmutable) seguido de
**[hechos de capítulos 1..N−1]** (crece por el final, nunca por el medio) y **[objetivo del capítulo
N]** al final convierte la mayor parte del prefill en lectura de caché.

Anthropic declara hasta −85 % de latencia y −80 % de TTFT en la parte cacheada.

**Cómo se verifica:** `usage.cache_read_input_tokens > 0` en `uso.jsonl`, que ya lo registramos. Si
hoy sale 0 o casi, está todo por ganar. **Primer paso: mirarlo antes de tocar nada.**

**Cuidado:** cambiar el `effort` a media conversación invalida la caché; el orden es
`tools → system → messages`, lo estable primero.

### 2. Apagar (o presupuestar) el thinking del extractor

No dará reloj medio --está solapado-- pero recorta coste y **aplana la cola**: si un capítulo del
escritor sale corto, el extractor deja de estar oculto y aparece en el camino crítico.

Evidencia: *OckBench* (2025) mide el «impuesto del sobrepensamiento», 3,3× tokens y 5× latencia entre
modelos pequeños de igual precisión; *TALE-EP*, −67 % de tokens con menos del 3 % de pérdida. Y Haiku
**no piensa si no se lo pides**: nuestros 6.000–11.000 tokens de razonamiento para entregar 1.200 son
thinking activado, no inevitable.

Riesgo acotado: el delta pasa por QA de todas formas.

### 3. Test de contradicción inyectada en QA

No es velocidad: es la validez de la métrica con la que decidimos todo lo demás.

Anthropic documenta el «problema de la victoria temprana»: verificadores que aprueban tras comprobar
lo mínimo. Nuestro «cero contradicciones» podría ser menos riguroso de lo que creemos.

**Cómo:** meter a mano una contradicción evidente en un capítulo cerrado y comprobar que el corte de
QA la marca y pausa la novela. Si no la caza, la mitad de las conclusiones de `HALLAZGOS.md` hay que
revisarlas.

### 4. Spec-X 05: aristas entre hechos

Ya especificado aparte. No es velocidad, es coherencia a partir del capítulo 10.

## Lo que nadie ha publicado

La investigación encontró arquitecturas gemelas --*Agents' Room* de DeepMind es prácticamente esta, y
hay dos repos de Claude Code casi idénticos-- pero **ninguno mide reloj ni camino crítico**, y casi
todos corren en serie donde aquí se solapa. No hay baseline externo contra el que compararse.
