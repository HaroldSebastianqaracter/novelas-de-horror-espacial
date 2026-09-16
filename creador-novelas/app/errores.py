"""Excepciones del harness: mapeo directo de la tabla de excepciones (spec funcional §7, spec técnica §7)."""


class HarnessError(Exception):
    """Base de todos los errores del harness."""


class EstadoInvalidoError(HarnessError):
    """EX-01: un artefacto de estado no valida contra su esquema."""


class PausadoPorQAError(HarnessError):
    """EX-02: la tanda está pausada por un reporte de QA sin resolver (RF-07.4)."""


class OutlineFaltanteError(HarnessError):
    """EX-03: falta la entrada de outline del capítulo N."""

    def __init__(self, n: int):
        super().__init__(f"EX-03: no existe la entrada de outline para el capítulo {n}")
        self.n = n


class ContextoExcedidoError(HarnessError):
    """EX-04: el contexto excede max_tokens_contexto_escritor incluso con el resumen rodante al mínimo."""

    def __init__(self, n: int, tokens: int, limite: int):
        super().__init__(
            f"EX-04: el contexto del capítulo {n} estima {tokens} tokens y el límite es {limite}; "
            "no se recorta continuidad.json ni personajes.json"
        )
        self.n, self.tokens, self.limite = n, tokens, limite


class ConfiguracionInvalidaError(HarnessError):
    """EX-05: un parámetro de configuración está fuera de rango o falta."""


class ConfiguracionInconsistenteError(HarnessError):
    """EX-06: total_capitulos cambió con capítulos ya cerrados."""


class LongitudFueraDeRangoAviso(Warning):
    """EX-07: el segundo intento también quedó fuera de +-20%; se acepta con aviso, la tanda sigue."""


class PersonajeNoPrevistoError(HarnessError):
    """EX-08: dos intentos seguidos introdujeron un personaje ausente del registro de sujetos."""

    def __init__(self, n: int, claves: list[str]):
        super().__init__(
            f"EX-08: el capítulo {n} introdujo personajes fuera del registro dos veces seguidas "
            f"({', '.join(claves)}); la entrada de outline es sospechosa"
        )
        self.n, self.claves = n, claves


class ContratoRetornoError(HarnessError):
    """RF-08.1: el mensaje final de un subagente no respeta su contrato de retorno."""


class AutovalidacionFallidaError(HarnessError):
    """EX-10: el agente agotó sus intentos de autovalidación (RF-08.4) y terminó informando el último error."""

    def __init__(self, rol: str, n: int | None, detalle: str):
        donde = f" del capítulo {n}" if n is not None else ""
        super().__init__(f"EX-10: el {rol} no consiguió validar su salida{donde}: {detalle}")
        self.rol, self.n, self.detalle = rol, n, detalle


class ManifiestoInconsistenteError(HarnessError):
    """§5: manifiesto editado a mano (en_progreso con reporte_qa_pendiente no nulo) u otra combinación imposible."""


class CapituloCerradoError(HarnessError):
    """INV-07: se intentó sobrescribir un capítulo ya cerrado."""
