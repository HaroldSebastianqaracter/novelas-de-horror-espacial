"""El puerto que invoca a Claude Code: interfaz, resultado y errores.

Es la unica abstraccion real del backend (RF-PUERTO-01). Absorbe como se invoca al motor de
agentes, y es lo que permite probar el orquestador entero sin gastar dinero ni depender de
la no determinacion de un agente.

Quien invoca es SIEMPRE el worker. Los router.py de FastAPI tienen prohibido importar esto
(RF-COD-05).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


class ErrorDePuerto(Exception):
    """Fallo al invocar al agente."""


class SalidaInvalida(ErrorDePuerto):
    """El agente respondio algo que no cumple el esquema pedido, dos veces."""

    def __init__(self, mensaje: str, *, salida_cruda: str = "", errores: str = "") -> None:
        super().__init__(mensaje)
        self.salida_cruda = salida_cruda
        self.errores = errores


class TiempoAgotado(ErrorDePuerto):
    """El agente supero el tiempo maximo por invocacion (RF-PUERTO-05)."""


class AgenteInterrumpido(ErrorDePuerto):
    """La invocacion se corto porque llego una intencion de parar (RF-PUERTO-06)."""


class AgenteUsoHerramientas(ErrorDePuerto):
    """El agente intento usar herramientas, que no tiene (RF2-PUERTO-10).

    Todo lo que necesita esta en el paquete. Si pide leer un fichero o ejecutar algo, esta
    buscando canon por su cuenta, que es justo lo que el principio 7 prohibe.
    """


class AgenteNoAutenticado(ErrorDePuerto):
    """Claude Code no esta autenticado en esta maquina (RF-PUERTO-09)."""


class SkillDesconocida(ErrorDePuerto):
    """No hay SKILL.md para ese agente, o la skill no es de ejecucion (RF-SKILL-03)."""


@dataclass(frozen=True)
class ResultadoAgente:
    """Lo que devuelve una invocacion, mas lo que la traza necesita para reproducirla."""

    agente: str
    salida: dict[str, Any]
    salida_cruda: str
    duracion_ms: int
    exit_code: int
    tokens_entrada: int = 0
    tokens_salida: int = 0
    coste_usd: float = 0.0
    num_turnos: int = 0
    llamada_id: int | None = None
    metadatos: dict[str, Any] = field(default_factory=dict)

    @property
    def hubo_compactacion(self) -> bool:
        """Senal de que Claude Code compacto o trunco dentro de la llamada (RF-PUERTO-08).

        Es el supuesto 2.5 de la spec: con el paquete bajo presupuesto y sin herramientas no
        deberia ocurrir. Si ocurre, queda registrado para poder contradecirlo.
        """
        marcas = ("compact", "truncat", "max_tokens")
        texto = " ".join(str(v) for v in self.metadatos.values()).lower()
        stop = str(self.metadatos.get("stop_reason", "")).lower()
        return any(m in texto for m in marcas) or stop == "max_tokens"


@runtime_checkable
class PuertoAgente(Protocol):
    """Una sola operacion: invocar a un agente y devolver su salida validada."""

    def invocar(
        self,
        agente: str,
        entrada: str,
        esquema_salida: dict[str, Any],
        *,
        timeout_s: int | None = None,
        novela_id: int | None = None,
        capitulo: int | None = None,
        intento: int | None = None,
        tokens_por_bloque: dict[str, int] | None = None,
    ) -> ResultadoAgente:
        """Ejecuta `agente` con `entrada` y devuelve su salida conforme a `esquema_salida`.

        `esquema_salida` es un JSON Schema (el que genera Pydantic con model_json_schema()).
        """
        ...

    def interrumpir(self, *, definitivo: bool = False) -> None:
        """Corta la invocacion en curso, si la hay.

        `definitivo` es lo que usa una senal de terminar (RF2-WK-09): ademas de cortar la
        llamada en curso, corta cualquier llamada posterior sin lanzarla.
        """
        ...
