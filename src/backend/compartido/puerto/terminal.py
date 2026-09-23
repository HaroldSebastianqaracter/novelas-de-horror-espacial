"""PuertoTerminal: invoca Claude Code como subproceso en modo no interactivo (RF-PUERTO-02).

Como se acota el contexto del agente, que es la pendiente mas urgente de la arquitectura:

  * La SKILL.md la leemos NOSOTROS y la inyectamos con `--system-prompt-file`, que SUSTITUYE
    el prompt de sistema. Asi no dependemos de que el modo no interactivo descubra skills.
  * `--tools ""` RETIRA las herramientas integradas, y `--allowedTools ""` les quita el
    permiso: el agente no puede leer ficheros, buscar ni ejecutar nada. `--strict-mcp-config`
    deja fuera los servidores MCP de la configuracion del usuario, que traerian las suyas.
    Todo lo que sabe esta en el paquete que le montamos (RF2-PUERTO-10).
  * Y se comprueba despues: una llamada con permisos denegados, o con mas turnos de los que
    necesita la salida estructurada, es un error, porque el agente intento usar algo.
  * El directorio de trabajo es un temporal VACIO, no la raiz del repo.
  * `--json-schema` obliga a que la salida cumpla el esquema y la devuelve ya parseada en
    `structured_output`.

Con eso el principio 7 —el contexto se selecciona, nunca se vuelca— se sostiene por
construccion y no por instruccion: la gestion de contexto de Claude Code no tiene nada que
leer por su cuenta.

Dos hechos verificados contra el binario instalado que conviene no perder:

  * `--bare` ROMPE LA AUTENTICACION: no lee las credenciales de la sesion y responde
    "Not logged in". No se usa.
  * La entrada va por STDIN, no como argumento: en Windows la linea de comandos tiene un
    techo de ~32.000 caracteres y un paquete de capitulo lo pasa de largo.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from ..db import transaccion
from ..tipos import como_dict, como_lista
from .base import (
    AgenteInterrumpido,
    AgenteNoAutenticado,
    AgenteUsoHerramientas,
    ErrorDePuerto,
    ResultadoAgente,
    SalidaInvalida,
    SkillDesconocida,
    TiempoAgotado,
)

# La skill de verificacion es de desarrollo, no de ejecucion (RF-SKILL-03).
SKILLS_PROHIBIDAS = frozenset({"verificacion"})

INTERVALO_SONDEO_S = 0.25



def _estimar_tokens(texto: str) -> int:
    """Estimacion determinista (RF-CTX-02). Sustituible por un tokenizador real."""
    return int(len(texto) / 3.5 * 1.1) + 1


def _extraer_json(texto: str) -> dict[str, Any] | None:
    """Saca el primer objeto JSON completo de un texto que puede traer ruido alrededor."""
    inicio = texto.find("{")
    while inicio != -1:
        profundidad = 0
        en_cadena = False
        escapado = False
        for i in range(inicio, len(texto)):
            c = texto[i]
            if en_cadena:
                if escapado:
                    escapado = False
                elif c == "\\":
                    escapado = True
                elif c == '"':
                    en_cadena = False
                continue
            if c == '"':
                en_cadena = True
            elif c == "{":
                profundidad += 1
            elif c == "}":
                profundidad -= 1
                if profundidad == 0:
                    try:
                        cargado = json.loads(texto[inicio : i + 1])
                    except json.JSONDecodeError:
                        break
                    objeto = como_dict(cargado)
                    if objeto or cargado == {}:
                        return objeto
                    break
        inicio = texto.find("{", inicio + 1)
    return None


def _uso_de_herramientas(sobre: dict[str, Any]) -> str:
    """Por que una respuesta delata que el agente intento usar herramientas, o '' si no."""
    denegados = como_lista(sobre.get("permission_denials"))
    if denegados:
        nombres = sorted({str(como_dict(d).get("tool_name", "?")) for d in denegados})
        return f"permisos denegados para {', '.join(nombres) or len(denegados)}"
    # `num_turns` no sirve de senal: una llamada real sin herramientas ha dado 2 y 3, segun
    # como el CLI reintente la salida estructurada (RF2-PUERTO-10). Se guarda en la traza.
    return ""


class PuertoTerminal:
    """Invoca a Claude Code como subproceso. Un puerto por worker."""

    def __init__(
        self,
        *,
        claude_bin: str = "claude",
        skills_dir: Path,
        timeout_agente_segundos: int = 1800,
        con: sqlite3.Connection | None = None,
    ) -> None:
        self.claude_bin = claude_bin
        self.skills_dir = Path(skills_dir)
        self.timeout_por_defecto = timeout_agente_segundos
        self.con = con
        self._proceso: subprocess.Popen[bytes] | None = None
        self._interrumpido = threading.Event()
        # Una senal de terminar cierra el puerto para siempre: el siguiente `invocar` no puede
        # limpiar la bandera y lanzar otra llamada (RF2-WK-09).
        self._cerrado = threading.Event()
        self._lock = threading.Lock()

    # -- skills ---------------------------------------------------------------------------

    def ruta_skill(self, agente: str) -> Path:
        if agente in SKILLS_PROHIBIDAS:
            raise SkillDesconocida(
                f"La skill '{agente}' es de desarrollo, no de ejecucion (RF-SKILL-03)."
            )
        ruta = self.skills_dir / agente / "SKILL.md"
        if not ruta.is_file():
            raise SkillDesconocida(f"No existe la skill del agente '{agente}': {ruta}")
        return ruta

    # -- traza ----------------------------------------------------------------------------

    def _abrir_traza(
        self,
        agente: str,
        sistema: str,
        entrada: str,
        esquema: dict[str, Any],
        novela_id: int | None,
        capitulo: int | None,
        intento: int | None,
        tokens_por_bloque: dict[str, int] | None,
    ) -> int | None:
        """Registra la llamada ANTES de lanzar el subproceso (RF-PUERTO-04)."""
        if self.con is None:
            return None
        with transaccion(self.con):
            cur = self.con.execute(
                """
                INSERT INTO llamada_modelo
                    (novela_id, agente, capitulo, intento, sistema, entrada, esquema,
                     tokens_entrada_por_bloque, tokens_entrada, estado)
                VALUES (?,?,?,?,?,?,?,?,?, 'en_curso')
                """,
                (
                    novela_id, agente, capitulo, intento, sistema, entrada,
                    json.dumps(esquema, ensure_ascii=False),
                    json.dumps(tokens_por_bloque or {}, ensure_ascii=False),
                    _estimar_tokens(sistema) + _estimar_tokens(entrada),
                ),
            )
            return int(cur.lastrowid or 0)

    def _cerrar_traza(
        self,
        llamada_id: int | None,
        *,
        estado: str,
        salida_cruda: str = "",
        tokens_salida: int = 0,
        duracion_ms: int = 0,
        exit_code: int | None = None,
        metadatos: dict[str, Any] | None = None,
    ) -> None:
        if self.con is None or llamada_id is None:
            return
        with transaccion(self.con):
            self.con.execute(
                """
                UPDATE llamada_modelo
                   SET estado = ?, salida_cruda = ?, tokens_salida = ?, duracion_ms = ?,
                       exit_code = ?, metadatos = ?, terminado_en = datetime('now')
                 WHERE id = ?
                """,
                (
                    estado, salida_cruda, tokens_salida, duracion_ms, exit_code,
                    json.dumps(metadatos or {}, ensure_ascii=False), llamada_id,
                ),
            )

    # -- invocacion -----------------------------------------------------------------------

    def _ejecutar(
        self, sistema_file: Path, entrada: str, esquema: dict[str, Any], timeout_s: int
    ) -> tuple[int, str, str, int]:
        """Lanza el subproceso y espera. Devuelve (exit_code, stdout, stderr, duracion_ms)."""
        cwd = Path(tempfile.mkdtemp(prefix="novelas-agente-"))
        orden = [
            self.claude_bin,
            "-p",
            "--system-prompt-file", str(sistema_file),
            "--tools", "",
            "--allowedTools", "",
            "--strict-mcp-config",
            "--output-format", "json",
            "--json-schema", json.dumps(esquema, ensure_ascii=False),
        ]

        entorno = dict(os.environ)
        entorno.pop("ANTHROPIC_API_KEY", None)  # RNF-06: ninguna clave pasa por el backend.

        comenzado = time.monotonic()
        try:
            with (
                tempfile.TemporaryFile() as f_out,
                tempfile.TemporaryFile() as f_err,
                tempfile.TemporaryFile() as f_in,
            ):
                f_in.write(entrada.encode("utf-8"))
                f_in.seek(0)
                proceso = subprocess.Popen(
                    orden, cwd=cwd, stdin=f_in, stdout=f_out, stderr=f_err, env=entorno
                )
                with self._lock:
                    self._proceso = proceso

                limite = comenzado + timeout_s
                while proceso.poll() is None:
                    if self._interrumpido.is_set() or self._cerrado.is_set():
                        proceso.kill()
                        proceso.wait(timeout=10)
                        raise AgenteInterrumpido("Invocacion cortada por una intencion de parar.")
                    if time.monotonic() > limite:
                        proceso.kill()
                        proceso.wait(timeout=10)
                        raise TiempoAgotado(f"El agente supero {timeout_s} s.")
                    time.sleep(INTERVALO_SONDEO_S)

                f_out.seek(0)
                f_err.seek(0)
                salida = f_out.read().decode("utf-8", errors="replace")
                error = f_err.read().decode("utf-8", errors="replace")
                return proceso.returncode, salida, error, int((time.monotonic() - comenzado) * 1000)
        finally:
            with self._lock:
                self._proceso = None
            shutil.rmtree(cwd, ignore_errors=True)

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
        if self._cerrado.is_set():
            raise AgenteInterrumpido("El puerto se cerro por una senal de terminar.")
        self._interrumpido.clear()
        timeout = timeout_s or self.timeout_por_defecto
        sistema = self.ruta_skill(agente).read_text(encoding="utf-8")

        llamada_id = self._abrir_traza(
            agente, sistema, entrada, esquema_salida, novela_id, capitulo, intento,
            tokens_por_bloque,
        )

        sistema_dir = Path(tempfile.mkdtemp(prefix="novelas-sistema-"))
        sistema_file = sistema_dir / "SKILL.md"
        sistema_file.write_text(sistema, encoding="utf-8")

        try:
            entrada_actual = entrada
            ultimo_error = ""
            # RF-PUERTO-03: una repeticion si la salida no cumple el esquema.
            for vuelta in (1, 2):
                try:
                    code, out, err, ms = self._ejecutar(
                        sistema_file, entrada_actual, esquema_salida, timeout
                    )
                except AgenteInterrumpido:
                    self._cerrar_traza(llamada_id, estado="interrumpida")
                    raise
                except TiempoAgotado:
                    self._cerrar_traza(llamada_id, estado="timeout")
                    raise

                sobre = _extraer_json(out) or {}
                resultado_txt = str(sobre.get("result", "") or "")
                metadatos = {
                    k: sobre.get(k)
                    # `modelUsage`: que modelo contesto y cuanto costo cada uno (RF3-OBS-10).
                    for k in ("subtype", "stop_reason", "num_turns", "total_cost_usd",
                              "session_id", "permission_denials", "usage", "modelUsage",
                              "terminal_reason")
                    if k in sobre
                }

                if sobre.get("is_error") or code != 0:
                    mensaje = resultado_txt or err or f"exit {code}"
                    if "not logged in" in mensaje.lower() or "/login" in mensaje.lower():
                        self._cerrar_traza(
                            llamada_id, estado="error", salida_cruda=out, duracion_ms=ms,
                            exit_code=code, metadatos=metadatos,
                        )
                        raise AgenteNoAutenticado(
                            "Claude Code no esta autenticado en esta maquina. "
                            f"Ejecuta 'claude' y usa /login. Detalle: {mensaje.strip()[:300]}"
                        )
                    ultimo_error = mensaje
                    if vuelta == 2:
                        self._cerrar_traza(
                            llamada_id, estado="error", salida_cruda=out, duracion_ms=ms,
                            exit_code=code, metadatos=metadatos,
                        )
                        raise ErrorDePuerto(
                            f"El agente '{agente}' fallo: {mensaje.strip()[:500]}"
                        )
                    entrada_actual = f"{entrada}\n\n[Intento anterior fallido: {mensaje[:500]}]"
                    continue

                uso_de_herramientas = _uso_de_herramientas(sobre)
                if uso_de_herramientas:
                    self._cerrar_traza(
                        llamada_id, estado="error", salida_cruda=out, duracion_ms=ms,
                        exit_code=code, metadatos=metadatos,
                    )
                    raise AgenteUsoHerramientas(
                        f"El agente '{agente}' intento usar herramientas: {uso_de_herramientas}"
                    )

                salida: dict[str, Any] | None = (
                    como_dict(sobre["structured_output"])
                    if isinstance(sobre.get("structured_output"), dict)
                    else _extraer_json(resultado_txt)
                )

                if not isinstance(salida, dict):
                    ultimo_error = "La respuesta no contiene un objeto JSON conforme al esquema."
                    if vuelta == 2:
                        self._cerrar_traza(
                            llamada_id, estado="salida_invalida", salida_cruda=out,
                            duracion_ms=ms, exit_code=code, metadatos=metadatos,
                        )
                        raise SalidaInvalida(
                            f"El agente '{agente}' no devolvio JSON valido.",
                            salida_cruda=out, errores=ultimo_error,
                        )
                    entrada_actual = (
                        f"{entrada}\n\n[Error de validacion del intento anterior: {ultimo_error} "
                        "Devuelve UNICAMENTE un objeto JSON conforme al esquema.]"
                    )
                    continue

                uso = como_dict(sobre.get("usage"))
                tokens_salida = int(uso.get("output_tokens") or _estimar_tokens(resultado_txt))
                tokens_entrada = int(uso.get("input_tokens") or 0)
                self._cerrar_traza(
                    llamada_id, estado="ok", salida_cruda=out, tokens_salida=tokens_salida,
                    duracion_ms=ms, exit_code=code, metadatos=metadatos,
                )
                return ResultadoAgente(
                    agente=agente,
                    salida=salida,
                    salida_cruda=out,
                    duracion_ms=ms,
                    exit_code=code,
                    tokens_entrada=tokens_entrada,
                    tokens_salida=tokens_salida,
                    coste_usd=float(sobre.get("total_cost_usd") or 0.0),
                    num_turnos=int(sobre.get("num_turns") or 0),
                    llamada_id=llamada_id,
                    metadatos=metadatos,
                )

            raise SalidaInvalida(f"El agente '{agente}' no produjo salida valida.",
                                 errores=ultimo_error)
        finally:
            shutil.rmtree(sistema_dir, ignore_errors=True)

    def interrumpir(self, *, definitivo: bool = False) -> None:
        """Corta la invocacion en curso (RF-PUERTO-06).

        Con `definitivo`, que es lo que manda una senal, ademas cierra el puerto: ninguna
        llamada posterior se lanza (RF2-WK-09).
        """
        self._interrumpido.set()
        if definitivo:
            self._cerrado.set()
        with self._lock:
            proceso = self._proceso
        if proceso is not None and proceso.poll() is None:
            proceso.kill()
