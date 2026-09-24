import { useQuery } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState } from "react";
import { errorDeCambio, LIMITES_CAMBIO, leerAlcance, type ObjetivoCambio } from "../../compartido/api/cambios";
import { consultaCanon, consultaHechosDeCapitulo, consultaUsosDeHecho, type EntidadLectura } from "../../compartido/api/consultas";
import { useIntenciones } from "../../compartido/api/intenciones";
import type { components } from "../../compartido/api/esquema.gen";
import { contieneTermino } from "./texto";

type VersionNovela = components["schemas"]["VersionNovela"];

interface Opcion {
  clave: string;
  etiqueta: string;
  objetivo: ObjetivoCambio;
  /** Para la estimación del alcance cuando la API no la da. */
  nombre?: string;
  hechoId?: number;
}

const ENTIDADES: readonly [EntidadLectura, string][] = [
  ["personajes", "personaje"],
  ["lugares", "lugar"],
  ["objetos", "objeto"],
];

const enumerar = (xs: number[]) =>
  xs.length === 1 ? `el capítulo ${xs[0]}` : `los capítulos ${xs.slice(0, -1).join(", ")} y ${xs.at(-1) ?? ""}`;

/**
 * Panel para pedir un cambio (RF-FE-CAM-02, RF-FE-CAM-03): sobre qué, qué cambiar y qué capítulos
 * se reescribirán, con confirmación en dos pasos. Al encolarse, lo sigue la franja del marco.
 */
export function PanelCambio({
  novelaId,
  capitulo,
  cita,
  version,
  alCerrar,
  alPedir,
}: {
  novelaId: number;
  capitulo: number;
  cita: string | null;
  version: VersionNovela;
  alCerrar: () => void;
  alPedir: (intencionId: number, peticion: string) => void;
}) {
  const id = useId();
  const titulo = useRef<HTMLHeadingElement>(null);
  const { pedir } = useIntenciones();
  const [elegida, setElegida] = useState<string | null>(null);
  const [peticion, setPeticion] = useState("");
  const [armado, setArmado] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => titulo.current?.focus(), []);

  const personajes = useQuery(consultaCanon(novelaId, "personajes"));
  const lugares = useQuery(consultaCanon(novelaId, "lugares"));
  const objetos = useQuery(consultaCanon(novelaId, "objetos"));
  const hechos = useQuery({ ...consultaHechosDeCapitulo(novelaId, capitulo), enabled: cita !== null });
  const canon = { personajes: personajes.data ?? [], lugares: lugares.data ?? [], objetos: objetos.data ?? [] };

  const opciones: Opcion[] = [];
  for (const [entidad, tipo] of ENTIDADES) {
    for (const e of canon[entidad]) {
      if (!("nombre" in e)) continue;
      if (cita === null || contieneTermino(cita, e.nombre)) {
        opciones.push({ clave: `${entidad}-${e.id}`, etiqueta: `${e.nombre} (${tipo})`, objetivo: { tipo: "entidad", entidad, id: e.id }, nombre: e.nombre });
      }
    }
  }
  if (cita !== null) {
    for (const h of hechos.data?.items ?? []) {
      if (h.vigente && (contieneTermino(cita, h.valor) || (h.sujeto_nombre && contieneTermino(cita, h.sujeto_nombre)))) {
        opciones.push({
          clave: `hecho-${h.id}`,
          etiqueta: `Un hecho: ${h.sujeto_nombre ?? ""} · ${h.atributo.replaceAll("_", " ")}: ${h.valor}`,
          objetivo: { tipo: "hecho", hecho_id: h.id },
          hechoId: h.id,
        });
      }
    }
    opciones.push({ clave: "fragmento", etiqueta: "El fragmento tal cual", objetivo: { tipo: "fragmento" } });
  }
  const opcion = opciones.find((o) => o.clave === elegida) ?? opciones[0];

  // Alcance: el de la API si lo da; si no, una estimación (RF-FE-CAM-03).
  const alcanceApi = useQuery({
    queryKey: ["novelas", novelaId, "cambios", "alcance", opcion?.clave],
    queryFn: () => leerAlcance(novelaId, opcion?.objetivo ?? { tipo: "fragmento" }) ?? Promise.resolve(null),
    enabled: !!opcion && opcion.objetivo.tipo !== "fragmento",
    retry: false,
  });
  const usos = useQuery({ ...consultaUsosDeHecho(novelaId, opcion?.hechoId ?? 0), enabled: !!opcion?.hechoId && alcanceApi.isError });
  let alcance: { capitulos: number[]; estimado: boolean } | null = null;
  if (alcanceApi.data) alcance = { capitulos: alcanceApi.data.capitulos, estimado: false };
  else if (alcanceApi.isError && opcion?.nombre) {
    const nombre = opcion.nombre;
    alcance = { capitulos: version.capitulos.filter((c) => contieneTermino(c.texto, nombre)).map((c) => c.numero), estimado: true };
  } else if (alcanceApi.isError && usos.data) {
    alcance = { capitulos: [...new Set(usos.data.map((u) => u.capitulo))].sort((a, b) => a - b), estimado: true };
  }

  const texto = peticion.trim();
  const peticionValida = texto.length >= LIMITES_CAMBIO.peticionMin && texto.length <= LIMITES_CAMBIO.peticionMax;
  const citaRecortada = cita?.slice(0, LIMITES_CAMBIO.citaMax) ?? null;

  const enviar = () => {
    if (!opcion || !peticionValida) return;
    if (!armado) {
      setArmado(true);
      return;
    }
    setEnviando(true);
    setError(null);
    pedir({
      tipo: "cambio_lector",
      novela_id: novelaId,
      payload: {
        version_base: version.numero,
        objetivo: opcion.objetivo,
        peticion: texto,
        ...(citaRecortada ? { cita: { capitulo, texto: citaRecortada } } : {}),
      },
    })
      .then((s) => alPedir(s.id, texto))
      .catch((e: unknown) => {
        const invalido = errorDeCambio(e);
        setError(invalido ? `${invalido.mensaje}${invalido.campos.length ? ` (${invalido.campos.join(", ")})` : ""}` : `No se pudo enviar: ${(e as Error).message}`);
        setArmado(false);
      })
      .finally(() => setEnviando(false));
  };

  return (
    <section className="panel-cambio" aria-labelledby={`${id}-titulo`}>
      <h2 id={`${id}-titulo`} ref={titulo} tabIndex={-1}>
        Pedir un cambio
      </h2>
      {citaRecortada ? (
        <blockquote className="panel-cambio__cita">
          {citaRecortada}
          {cita && cita.length > LIMITES_CAMBIO.citaMax && "…"}
        </blockquote>
      ) : (
        <p className="panel-cambio__pista">Sin fragmento: elige sobre quién o qué es el cambio. También puedes seleccionar texto del capítulo.</p>
      )}
      <form
        onKeyDown={(e) => {
          if (e.key === "Escape") setArmado(false);
        }}
        onSubmit={(e) => {
          e.preventDefault();
          enviar();
        }}
      >
        <fieldset className="panel-cambio__objetivos" disabled={enviando}>
          <legend>¿Sobre qué?</legend>
          {opciones.length === 0 ? (
            <p className="panel-cambio__pista">Cargando el canon…</p>
          ) : (
            opciones.map((o) => (
              <label key={o.clave} className="panel-cambio__opcion">
                <input
                  type="radio"
                  name={`${id}-objetivo`}
                  checked={o.clave === opcion?.clave}
                  onChange={() => {
                    setElegida(o.clave);
                    setArmado(false);
                  }}
                />
                {o.etiqueta}
              </label>
            ))
          )}
        </fieldset>
        <label className="panel-cambio__peticion">
          Qué quieres cambiar
          <textarea
            value={peticion}
            maxLength={LIMITES_CAMBIO.peticionMax}
            rows={2}
            placeholder="Por ejemplo: el perro se llama Nala"
            disabled={enviando}
            aria-describedby={`${id}-cuenta`}
            onChange={(e) => {
              setPeticion(e.target.value);
              setArmado(false);
            }}
          />
          <span id={`${id}-cuenta`} className="panel-cambio__cuenta">
            {texto.length} de {LIMITES_CAMBIO.peticionMax} caracteres{texto.length > 0 && texto.length < LIMITES_CAMBIO.peticionMin ? ` · al menos ${LIMITES_CAMBIO.peticionMin}` : ""}
          </span>
        </label>
        <p className="panel-cambio__alcance" role="status">
          {opcion?.objetivo.tipo === "fragmento"
            ? `Se reescribirá el capítulo ${capitulo} y los que dependan de lo que cambie; lo decide el worker.`
            : alcance
              ? alcance.capitulos.length
                ? `Se reescribirán ${enumerar(alcance.capitulos)}${alcance.estimado ? " (estimación)" : ""}.`
                : `No se reescribirá ningún capítulo${alcance.estimado ? " (estimación)" : ""}.`
              : opcion
                ? "Calculando qué capítulos se reescribirán…"
                : ""}
        </p>
        {armado && (
          <p className="panel-cambio__aviso">
            Reescribir capítulos lleva un rato y, con Claude Code de verdad, cuesta dinero. Se publicará una versión nueva y
            la actual seguirá disponible.
          </p>
        )}
        {error && (
          <p className="aviso aviso--error" role="alert">
            {error}
          </p>
        )}
        <div className="panel-cambio__acciones">
          <button type="submit" className="boton boton--primario" disabled={!opcion || !peticionValida || enviando}>
            {enviando ? "Enviando…" : armado ? "Confirmar: pedir el cambio" : "Pedir el cambio"}
          </button>
          <button type="button" className="boton" onClick={alCerrar} disabled={enviando}>
            Cancelar
          </button>
        </div>
      </form>
    </section>
  );
}
