"""Corre el banco de contraejemplos de la puerta 3 e imprime la tabla (specs/spec3.md, RF3-BAN-05).

Uso, desde src/backend:

    .venv\\Scripts\\python.exe banco_contraejemplos.py

Trabaja sobre bases temporales con el puerto falso: no cuesta nada y no toca ninguna base del
autor. Sale con 1 si algun caso no hace lo que el banco dice que hace hoy.
"""

from __future__ import annotations

import sys

from evals import banco_puerta3


def main() -> int:
    informe = banco_puerta3.correr()
    print(informe.tabla())
    for r in informe.desviados:
        print(f"DESVIADO {r.caso.id}: bloqueantes {sorted(r.bloqueantes)}, "
              f"avisos {sorted(r.avisos)}")
    return 1 if informe.desviados else 0


if __name__ == "__main__":
    # La consola de Windows no es UTF-8 y la tabla lleva tildes y rayas.
    reconfigurar = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigurar):
        reconfigurar(encoding="utf-8")
    sys.exit(main())
