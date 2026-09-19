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

### 1. Test de contradicción inyectada en QA

No es velocidad: es la validez de la métrica con la que decidimos todo lo demás.

Anthropic documenta el «problema de la victoria temprana»: verificadores que aprueban tras comprobar
lo mínimo. Nuestro «cero contradicciones» podría ser menos riguroso de lo que creemos, y toda la
columna `contradicciones` del CSV cuelga de que el corte de QA cace lo que decimos que caza.

**Cómo:** meter a mano una contradicción evidente en un capítulo cerrado y comprobar que el corte de
QA la marca y pausa la novela. Si no la caza, la mitad de las conclusiones de `HALLAZGOS.md` hay que
revisarlas.

Estaba en tercer lugar. Sube al primero porque el que estaba primero se cayó: ver el punto 3.

### 2. Apagar (o presupuestar) el thinking del extractor

No dará reloj medio --está solapado-- pero recorta coste y **aplana la cola**: si un capítulo del
escritor sale corto, el extractor deja de estar oculto y aparece en el camino crítico.

Evidencia: *OckBench* (2025) mide el «impuesto del sobrepensamiento», 3,3× tokens y 5× latencia entre
modelos pequeños de igual precisión; *TALE-EP*, −67 % de tokens con menos del 3 % de pérdida. Y Haiku
**no piensa si no se lo pides**: nuestros 6.000–11.000 tokens de razonamiento para entregar 1.200 son
thinking activado, no inevitable.

Riesgo acotado: el delta pasa por QA de todas formas.

### 3. Reordenar prefijos: queda poco que ganar

Era la apuesta principal, y **la medición la desinfla**. Agregando `uso.jsonl` de las 23 novelas
archivadas, por rol:

| rol | invocaciones | lee de caché | crea caché | entrada fresca | % leído |
|---|---|---|---|---|---|
| escritor | 103 | 9.443.588 | 2.362.593 | 866 | 80,0 % |
| qa | 72 | 6.761.824 | 1.740.745 | 642 | 79,5 % |
| extractor | 59 | 4.425.411 | 1.253.090 | 2.099 | 77,9 % |
| orquestador | 148 | 62.805.671 | 1.056.602 | 609 | 98,3 % |

La hipótesis era «si sale 0, está todo por ganar». Sale 80 %. La entrada fresca del escritor son
**866 tokens en 103 invocaciones**: ocho por llamada. El prompt ya entra por caché casi entero, así
que el desorden del estado que sospechábamos, o no existe, o cae en la parte que de todas formas
habría que crear.

Lo que queda es el 20 % de creación: unos 23.000 tokens de prefill por invocación del escritor. Parte
es inevitable --cada subagente es una sesión nueva y su propio turno anterior nunca está cacheado-- y
parte sí es reordenable, pero el techo son unos segundos por llamada, tres en el escritor y tres en
QA: del orden del 2–3 % del reloj. No justifica tocar la construcción del prompt todavía.

### 4. Spec-X 05: aristas entre hechos

Ya especificado aparte. No es velocidad, es coherencia a partir del capítulo 10.

## Lo que nadie ha publicado

La investigación encontró arquitecturas gemelas --*Agents' Room* de DeepMind es prácticamente esta, y
hay dos repos de Claude Code casi idénticos-- pero **ninguno mide reloj ni camino crítico**, y casi
todos corren en serie donde aquí se solapa. No hay baseline externo contra el que compararse.
