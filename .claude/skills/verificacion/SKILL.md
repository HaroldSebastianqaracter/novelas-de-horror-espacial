---
name: verificacion
description: Construye o actualiza el plan de verificación (verification.md) de una spec, un componente de src/ o la salida de un agente — qué propiedades importan, con qué método se comprueba cada una y con qué etiqueta del Trust Spec (T/A/I/D/U). Úsala al escribir o revisar una spec, antes de dar por terminado un componente, al decidir qué tests o evals hacen falta, y cuando haya que dejar por escrito un riesgo aceptado.
---

# Plan de verificación

El catálogo de métodos y la clasificación Trust Spec viven en [`docs/validators.md`](../../../docs/validators.md). Es la única fuente: léelo antes de asignar nada y no inventes métodos fuera de él. Si falta un método que el proyecto necesita, eso es un cambio en `docs/` y se entrevista con `grillme` antes de tocarlo (ver `AGENTS.md`).

Esta skill produce un artefacto: `specs/<nombre-de-la-spec>-verification.md`, hermano de la spec que verifica. Un componente de `src/` sin spec no se verifica: primero se escribe su spec.

## Pasos

### 1. Delimitar el alcance

Nombra exactamente qué se verifica y de qué tipo es cada parte:

- **Determinista** — código de `src/`: API, esquemas, transformaciones, persistencia, UI.
- **No determinista** — lo que un agente decide o escribe: trayectoria de herramientas, texto generado, coherencia con la ontología de [`docs/definitions.md`](../../../docs/definitions.md).

La mezcla es lo normal. Separarla es lo que decide qué mitad del catálogo aplica.

### 2. Enumerar las propiedades que importan

Una propiedad es una afirmación que puede ser falsa. "Autenticación" no lo es; "un usuario sin sesión nunca recibe el cuerpo de un capítulo" sí.

Barre estas fuentes hasta agotarlas:

- Lo que la spec promete, cláusula a cláusula.
- Los límites: entradas vacías, máximos, concurrencia, fallo de dependencias.
- Los invariantes que deben cumplirse siempre, incluido el orden ("nunca publicar antes de validar").
- El modelo de amenaza: prompt injection, mal uso de herramientas, goal drift, exfiltración.
- Las propiedades de la salida narrativa: continuidad, voz, cumplimiento de las reglas de [`docs/domain-knowledge.md`](../../../docs/domain-knowledge.md).

Criterio de fin: toda promesa de la spec aparece como al menos una propiedad, y cada propiedad se puede afirmar o negar sin discutir qué significa.

### 3. Asignar método y etiqueta

Para cada propiedad, elige del catálogo el método más barato que dé evidencia real, y arrastra su etiqueta.

Reglas de asignación:

- Una propiedad que un tipo ya garantiza no necesita un test (`A` antes que `T`).
- Una propiedad sobre texto generado no se cubre con un test de ejemplo: va a evals, y la etiqueta es `I` si el scorer es un modelo juez.
- Un invariante de orden en un flujo multi-agente es `model checking` (`A`), no un test de integración.
- Contención (sandbox, guardrails, rollout progresivo) es `D`: la evidencia es observar que bloquea, no que el código exista.
- Una propiedad puede llevar dos métodos cuando cada uno cubre una mitad distinta; escribe los dos.

Lo que no puedas verificar se etiqueta `U` con motivo y con qué lo hace tolerable (impacto bajo, reversible, detectable en producción). `U` es una decisión escrita, no un hueco.

Criterio de fin: cero propiedades sin etiqueta.

### 4. Escribir el archivo

```markdown
# Verificación — <nombre de la spec>

Plan de verificación de [`<spec>.md`](<spec>.md). Métodos y etiquetas según [`docs/validators.md`](../docs/validators.md).

## Propiedades verificadas

| # | Propiedad | Método | Tag | Evidencia | Estado |
| --- | --- | --- | --- | --- | --- |
| 1 | Un usuario sin sesión nunca recibe el cuerpo de un capítulo | Integration testing | `T` | `tests/api/test_chapters.py` | pendiente |

## Riesgos aceptados

| # | Propiedad | Por qué no se verifica | Qué lo hace tolerable |
| --- | --- | --- | --- |
| 7 | La prosa mantiene la voz del narrador entre sesiones largas | No hay scorer fiable todavía | Revisión humana antes de publicar |
```

**Evidencia** apunta a dónde vive la comprobación (archivo de test, suite de evals, dashboard, paso del pipeline) o `—` si aún no existe. **Estado** es `pendiente`, `implementado` o `fallando`.

### 5. Cerrar

Revisa contra estas cuatro condiciones antes de darlo por hecho:

1. Cada promesa de la spec está en la tabla.
2. Cada fila lleva un método del catálogo, escrito con su nombre del catálogo.
3. Cada `U` tiene motivo y atenuante.
4. El plan entra en el mismo commit que la spec y el código, como manda `AGENTS.md`.

## Al revisar un plan existente

No lo reescribas: dilo en tres frentes.

- **Optimismo de etiqueta** — una fila marcada `T` cuya evidencia no existe, o marcada `A` cuando el tipo no garantiza esa propiedad.
- **Propiedades que faltan** — la spec cambió y la tabla no.
- **`U` disfrazado** — una propiedad que nadie comprueba pero aparece como verificada. Bájala a la tabla de riesgos aceptados.
