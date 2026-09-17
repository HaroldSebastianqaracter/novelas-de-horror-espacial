# Poner el harness en marcha en una máquina nueva

Lo que hay que tener instalado, y una trampa de Windows que conviene conocer antes de lanzar
nada porque falla en silencio.

## Requisitos

| Qué | Por qué |
|---|---|
| Python 3.11 o superior, con el entorno en `.venv/` | Todo se ejecuta como `.venv/Scripts/python.exe -m app <verbo>`, nunca `python` a secas |
| Claude Code (`claude` en el PATH) | Las fases que invocan agentes se lanzan con él |
| Git | El control de versiones, y en Windows además hace falta para los hooks: ver abajo |

```
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[test]"
.venv/Scripts/python.exe -m pytest -q
```

Las dependencias están en `pyproject.toml`: `pydantic` y `tiktoken`, más `pytest` para las
pruebas. Si la instalación funcionó, la suite pasa entera.

## La trampa de Windows: los hooks necesitan Git Bash

En Windows, Claude Code ejecuta los comandos de los hooks a través del `bash.exe` que trae Git
para Windows. Lo busca en la ruta de una instalación **para todos los usuarios**:

```
C:\Program Files\Git\bin\bash.exe
```

Si Git se instaló **solo para el usuario actual**, que es lo que ocurre cuando no hay permisos de
administrador, queda en otro sitio y ahí no lo encuentra:

```
%LOCALAPPDATA%\Programs\Git\bin\bash.exe
```

**Tener `git` en el PATH no basta.** Claude Code no deduce la ruta de `bash.exe` a partir del
`git.exe` que encuentra en el PATH.

### Por qué importa tanto

Cuando no encuentra `bash.exe`, los hooks **no dan error: simplemente no se ejecutan**. Y los
hooks son la valla de invariantes de este harness:

- **H-06** confina las escrituras de cada agente a su propio archivo (INV-01, INV-05, RF-07.5).
- **H-10** registra los tokens de cada invocación en `uso.jsonl`, que es de donde sale el coste.
- **H-11** acota la terminal de cada agente a su único comando de validación.

Sin ellos la tanda parece correr bien, porque los verbos del CLI validan por su cuenta, pero se
ejecuta sin protección y sin registro de uso. Pasó de verdad el 17/09/2026: una tanda de 28
minutos y 8 $ terminó sin un solo evento de hook y nada lo delató.

### Qué hace el harness al respecto

La pantalla de producción resuelve la ruta por su cuenta antes de lanzar una fase: mira la
variable de entorno, luego el `git` del PATH, luego las ubicaciones conocidas. Si no la
encuentra, **se niega a lanzar** en vez de correr sin valla.

Eso cubre las fases lanzadas desde la web. **No cubre las sesiones interactivas**: si vas a
escribir `/escribir-tanda` a mano en una terminal, define la variable en tu usuario de Windows.

```
setx CLAUDE_CODE_GIT_BASH_PATH "%LOCALAPPDATA%\Programs\Git\bin\bash.exe"
```

Abre una terminal nueva después: `setx` no afecta a las que ya estaban abiertas.

### Cómo comprobar que los hooks están vivos

Lanza una escritura cualquiera con Claude Code y mira si quedó anotada:

```
.venv/Scripts/python.exe -m app status
```

En `07_registro/<carpeta actual>/eventos.jsonl` tiene que haber líneas con `"tipo": "hook"`.
Si no hay ninguna después de que un agente haya escrito algo, los hooks no están corriendo.

## Credenciales

Las claves van **solo en variables de entorno**, nunca en `config/`, en `settings.json` ni en
ningún archivo del repositorio:

- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` para publicar las trazas
  (`python -m app exportar-traza ultima`).

Sin ellas el harness funciona igual; lo único que no hay es observabilidad.

## Arrancar

```
.venv/Scripts/python.exe -m app ui
```

Abre `http://127.0.0.1:8765`. Desde ahí se encarga el libro, se lanzan las fases y se lee lo
escrito, sin tocar la terminal.
