# Architecture — Sistema de agentes

## Estructura del monorepo

El proyecto es un monorepo con estas carpetas principales:

- **`src/`** — todo el código del programa.
  - **`src/backend/`** — FastAPI + Python.
  - **`src/frontend/`** — React + Three.js.
- **`specs/`** — especificaciones del programa, una por `.md`.
- **`docs/`** — definiciones del proyecto (este documento entre ellas).

`src/backend/` y `src/frontend/` están creadas pero sin scaffolding todavía; ver sus respectivos `README.md` para el estado actual.

## Sistema de agentes

_Pendiente. Todavía no se ha diseñado la arquitectura del sistema de agentes generador de novelas (qué agentes existen, qué produce cada uno, cómo se pasan el contexto entre sí). Este documento se completará cuando definamos esa parte del proyecto._
