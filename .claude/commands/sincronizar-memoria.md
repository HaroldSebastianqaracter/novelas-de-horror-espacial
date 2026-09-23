---
description: Copia la memoria de Claude Code de este proyecto a .claude/memoria/ para que quede commiteada
---

La memoria automática de Claude Code vive fuera del repo, en `~/.claude/projects/<proyecto>/memory/`. La entrega del examen pide que esté commiteada, así que este comando deja una copia en `.claude/memoria/`.

1. Localiza el directorio de memoria de este proyecto dentro de `~/.claude/projects/`.
2. Copia todos sus `.md` a `.claude/memoria/`, sustituyendo los que ya existan. Borra de `.claude/memoria/` los que ya no estén en el origen, salvo `README.md`.
3. Revisa cada fichero copiado antes de darlo por bueno: nada de claves, tokens ni datos personales de terceros. Si encuentras algo, no lo copies y avisa.

Devuelve la lista de ficheros añadidos, actualizados y borrados. No hagas commit: lo decide el autor.
