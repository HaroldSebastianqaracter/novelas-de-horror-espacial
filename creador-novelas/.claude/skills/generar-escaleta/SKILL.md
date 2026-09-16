---
name: generar-escaleta
description: Fase 3 (RF-03.1, RF-03.2). Genera 04_estado/capitulos.json con total_capitulos entradas, títulos únicos y curva de tensión con máximo en el tercio final. Crea el manifiesto.
allowed-tools: Read, Write, Bash(.venv/Scripts/python.exe -m harness:*)
disable-model-invocation: true
---

Configuración:
!`cat config/novela.json`

Premisa:
!`cat 01_concepto/premisa.md 2>/dev/null || echo "(falta premisa.md)"`

Sinopsis:
!`cat 04_estado/tres_actos.md 2>/dev/null || echo "(falta tres_actos.md: corré /generar-sinopsis)"`

# Fase 3: escaleta de capítulos

Condición de entrada: `tres_actos.md` y `premisa.md` existen. Si `04_estado/manifest.json` ya existe con `ultimo_capitulo_cerrado > 0`, detenete: la escaleta es inmutable (INV-04).

Pasos:
1. Generá un array JSON con **exactamente `total_capitulos` entradas** (de `config/novela.json`), `num` consecutivo desde 1, y por entrada: `num`, `titulo`, `objetivo_narrativo`, `personajes` (lista de nombres canónicos, siempre el mismo nombre para el mismo personaje), `locacion` (nombre canónico, reutilizado entre capítulos), `informacion_nueva`, `tension` (entero 1-5).
2. Los títulos se generan acá, no en el escritor (RF-03.1): estilo consistente, ninguno vacío ni repetido.
3. Curva de tensión (RF-03.2): no monótonamente decreciente y con el **máximo en el tercio final**. Respirá con niveles 1-2 entre picos.
4. Cada personaje con nombre que vaya a aparecer en la novela debe figurar en `personajes` de al menos una entrada: la fase 4 crea las fichas a partir de esta lista y el escritor no puede inventar otros (EX-08).
5. Guardá con Write en `.tanda/borradores/capitulos.json` y persistí con
   `.venv/Scripts/python.exe -m harness guardar outline --desde .tanda/borradores/capitulos.json`
   `guardar` valida el esquema, la cantidad, la unicidad de títulos y la curva; si falla, corregí exactamente eso y repetí.

Retorno: una línea con la ruta escrita, la cantidad de entradas y el capítulo donde cae el máximo de tensión.
