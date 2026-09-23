import type { ReactNode } from "react";
import {
  INTENSIDADES,
  type Intensidad,
  LIMITES,
  OCASIONES,
  PRONOMBRES,
  SUBGENEROS,
  TONOS,
} from "../../compartido/api/brief";
import {
  type AllegadoBorrador,
  allegadoVacio,
  type Borrador,
  type ElementoBorrador,
  elementoVacio,
  type Errores,
} from "./borrador";

export const ETIQUETA_PRONOMBRES = { el: "Él", ella: "Ella", neutro: "Neutro" } as const;
export const ETIQUETA_OCASION = {
  cumpleanos: "Cumpleaños",
  aniversario: "Aniversario",
  boda: "Boda",
  jubilacion: "Jubilación",
  navidad: "Navidad",
  otra: "Otra",
} as const;
export const ETIQUETA_INTENSIDAD: Record<Intensidad, string> = {
  atmosferico: "Atmosférico",
  tension: "Tensión",
  intenso: "Intenso",
};
export const ETIQUETA_TONO = {
  sobrio: ["Sobrio", "Contenido, sin adornos"],
  emotivo: ["Emotivo", "El vínculo pesa tanto como el miedo"],
  humor_negro: ["Humor negro", "El miedo con una sonrisa torcida"],
  aventura: ["Aventura", "Ritmo, huida y hazaña"],
} as const;
export const ETIQUETA_SUBGENERO = {
  terror_corporal: "Terror corporal",
  infeccion: "Infección",
  horror_cosmico: "Horror cósmico",
  slasher_espacial: "Slasher espacial",
  ia_hostil: "IA hostil",
  supervivencia: "Supervivencia",
} as const;

export interface PropsPaso {
  borrador: Borrador;
  actualizar: (cambios: Partial<Borrador>) => void;
  errores: Errores;
}

/** Un campo con su etiqueta, su pista y sus errores, enlazados por `aria-describedby`. */
function Campo({
  id,
  etiqueta,
  obligatorio,
  pista,
  errores,
  children,
}: {
  id: string;
  etiqueta: string;
  obligatorio?: boolean;
  pista?: ReactNode;
  errores?: string[];
  children: (describir: { "aria-describedby"?: string; "aria-invalid"?: boolean }) => ReactNode;
}) {
  const ids = [pista ? `p-${id}` : null, errores?.length ? `e-${id}` : null].filter(Boolean).join(" ");
  return (
    <div className="campo" data-error={errores?.length ? true : undefined}>
      <label className="campo__etiqueta" htmlFor={id}>
        {etiqueta} <Marca obligatorio={obligatorio} />
      </label>
      {children({ "aria-describedby": ids || undefined, "aria-invalid": errores?.length ? true : undefined })}
      {pista && (
        <p className="campo__pista" id={`p-${id}`}>
          {pista}
        </p>
      )}
      <ErroresDe id={`e-${id}`} errores={errores} />
    </div>
  );
}

function Marca({ obligatorio }: { obligatorio?: boolean }) {
  return obligatorio ? <span className="campo__req">obligatorio</span> : <span className="campo__opc">opcional</span>;
}

function ErroresDe({ id, errores }: { id: string; errores?: string[] }) {
  if (!errores?.length) return null;
  return (
    <ul className="campo__error" id={id}>
      {[...new Set(errores)].map((e) => (
        <li key={e}>{e}</li>
      ))}
    </ul>
  );
}

/** Un grupo con leyenda (radios o listas), con sus errores bajo la leyenda. */
function Grupo({
  id,
  leyenda,
  obligatorio,
  pista,
  errores,
  children,
}: {
  id: string;
  leyenda: string;
  obligatorio?: boolean;
  pista?: ReactNode;
  errores?: string[];
  children: ReactNode;
}) {
  const ids = [pista ? `p-${id}` : null, errores?.length ? `e-${id}` : null].filter(Boolean).join(" ");
  return (
    <fieldset className="campo campo--grupo" id={id} data-error={errores?.length ? true : undefined} aria-describedby={ids || undefined}>
      <legend className="campo__etiqueta">
        {leyenda} <Marca obligatorio={obligatorio} />
      </legend>
      {pista && (
        <p className="campo__pista" id={`p-${id}`}>
          {pista}
        </p>
      )}
      <ErroresDe id={`e-${id}`} errores={errores} />
      {children}
    </fieldset>
  );
}

function ListaElementos({
  nombre,
  singular,
  elementos,
  maximo,
  alCambiar,
}: {
  nombre: string;
  singular: string;
  elementos: ElementoBorrador[];
  maximo: number;
  alCambiar: (xs: ElementoBorrador[]) => void;
}) {
  const cambiar = (id: string, cambios: Partial<ElementoBorrador>) =>
    alCambiar(elementos.map((e) => (e.id === id ? { ...e, ...cambios } : e)));
  return (
    <div className="elementos">
      {elementos.map((e, i) => (
        <div key={e.id} className="elemento">
          <label className="solo-lectores" htmlFor={`${nombre}-${e.id}`}>
            {singular} {i + 1}
          </label>
          <input
            id={`${nombre}-${e.id}`}
            className="campo__control"
            value={e.texto}
            maxLength={LIMITES.textoElemento}
            onChange={(ev) => cambiar(e.id, { texto: ev.target.value })}
          />
          <label className="elemento__obligatorio">
            <input type="checkbox" checked={e.obligatorio} onChange={(ev) => cambiar(e.id, { obligatorio: ev.target.checked })} />
            Obligatorio
          </label>
          <button
            type="button"
            className="boton boton--mini"
            aria-label={`Quitar ${singular.toLowerCase()} ${i + 1}`}
            onClick={() => alCambiar(elementos.filter((x) => x.id !== e.id))}
          >
            Quitar
          </button>
        </div>
      ))}
      <button
        type="button"
        className="boton boton--mini"
        disabled={elementos.length >= maximo}
        onClick={() => alCambiar([...elementos, elementoVacio()])}
      >
        + Añadir {singular.toLowerCase()}
      </button>
    </div>
  );
}

export function PasoDestinatario({ borrador, actualizar, errores }: PropsPaso) {
  return (
    <>
      <Campo id="f-nombre" etiqueta="Nombre" obligatorio errores={errores["destinatario.nombre"]} pista="Se escribirá exactamente así en toda la novela.">
        {(a) => (
          <input
            id="f-nombre"
            className="campo__control"
            value={borrador.nombre}
            maxLength={LIMITES.nombre}
            autoComplete="off"
            onChange={(e) => actualizar({ nombre: e.target.value })}
            {...a}
          />
        )}
      </Campo>
      <Campo id="f-edad" etiqueta="Edad" obligatorio errores={errores["destinatario.edad"]} pista="La del lector: la novela es para esta persona.">
        {(a) => (
          <input
            id="f-edad"
            className="campo__control campo__control--num"
            inputMode="numeric"
            value={borrador.edad}
            onChange={(e) => actualizar({ edad: e.target.value })}
            {...a}
          />
        )}
      </Campo>
      <Grupo id="g-pronombres" leyenda="Pronombres" obligatorio errores={errores["destinatario.pronombres"]}>
        <div className="radios radios--tres">
          {PRONOMBRES.map((p) => (
            <label key={p} className="opcion-radio">
              <input
                type="radio"
                name="pronombres"
                value={p}
                checked={borrador.pronombres === p}
                onChange={() => actualizar({ pronombres: p })}
              />
              <span className="opcion-radio__caja">
                <span className="opcion-radio__nombre">{ETIQUETA_PRONOMBRES[p]}</span>
              </span>
            </label>
          ))}
        </div>
      </Grupo>
      <Grupo
        id="g-rasgos"
        leyenda="Rasgos"
        obligatorio
        errores={errores["destinatario.rasgos"]}
        pista={`De carácter o físicos, de 1 a ${LIMITES.rasgos}. Los obligatorios tienen que aparecer en la novela.`}
      >
        <ListaElementos
          nombre="rasgo"
          singular="Rasgo"
          elementos={borrador.rasgos}
          maximo={LIMITES.rasgos}
          alCambiar={(rasgos) => actualizar({ rasgos })}
        />
      </Grupo>
    </>
  );
}

export function PasoMundo({ borrador, actualizar, errores }: PropsPaso) {
  const cambiarAllegado = (id: string, cambios: Partial<AllegadoBorrador>) =>
    actualizar({ allegados: borrador.allegados.map((a) => (a.id === id ? { ...a, ...cambios } : a)) });
  return (
    <>
      <Grupo
        id="g-recuerdos"
        leyenda="Recuerdos"
        obligatorio
        errores={errores.recuerdos}
        pista={`Anécdotas, lugares, costumbres, de 1 a ${LIMITES.recuerdos}. Se trasladan a la estación.`}
      >
        <ListaElementos
          nombre="recuerdo"
          singular="Recuerdo"
          elementos={borrador.recuerdos}
          maximo={LIMITES.recuerdos}
          alCambiar={(recuerdos) => actualizar({ recuerdos })}
        />
      </Grupo>
      <Grupo
        id="g-allegados"
        leyenda="Allegados"
        errores={errores.allegados}
        pista={`Personas o mascotas cercanas, hasta ${LIMITES.allegados}. Entran en el elenco.`}
      >
        <div className="allegados">
          {borrador.allegados.map((a, i) => (
            <div key={a.id} className="allegado">
              <p className="allegado__titulo">Allegado {i + 1}</p>
              <label>
                Nombre
                <input className="campo__control" value={a.nombre} maxLength={LIMITES.nombreAllegado} onChange={(e) => cambiarAllegado(a.id, { nombre: e.target.value })} />
              </label>
              <label>
                Relación
                <input
                  className="campo__control"
                  value={a.relacion}
                  maxLength={LIMITES.relacion}
                  placeholder="su hermano, su perra…"
                  onChange={(e) => cambiarAllegado(a.id, { relacion: e.target.value })}
                />
              </label>
              <label className="allegado__ancho">
                Rasgos, separados por comas (hasta {LIMITES.rasgosAllegado})
                <input className="campo__control" value={a.rasgos} onChange={(e) => cambiarAllegado(a.id, { rasgos: e.target.value })} />
              </label>
              <label className="elemento__obligatorio">
                <input type="checkbox" checked={a.obligatorio} onChange={(e) => cambiarAllegado(a.id, { obligatorio: e.target.checked })} />
                Obligatorio
              </label>
              <button
                type="button"
                className="boton boton--mini"
                aria-label={`Quitar allegado ${i + 1}`}
                onClick={() => actualizar({ allegados: borrador.allegados.filter((x) => x.id !== a.id) })}
              >
                Quitar
              </button>
            </div>
          ))}
          <button
            type="button"
            className="boton boton--mini"
            disabled={borrador.allegados.length >= LIMITES.allegados}
            onClick={() => actualizar({ allegados: [...borrador.allegados, allegadoVacio()] })}
          >
            + Añadir allegado
          </button>
        </div>
      </Grupo>
    </>
  );
}

export function PasoEncargo({ borrador, actualizar, errores }: PropsPaso) {
  return (
    <>
      <Campo id="f-ocasion" etiqueta="Ocasión" obligatorio errores={errores.ocasion}>
        {(a) => (
          <select
            id="f-ocasion"
            className="campo__control campo__control--medio"
            value={borrador.ocasion}
            onChange={(e) => actualizar({ ocasion: e.target.value as Borrador["ocasion"] })}
            {...a}
          >
            <option value="">Elige una ocasión</option>
            {OCASIONES.map((o) => (
              <option key={o} value={o}>
                {ETIQUETA_OCASION[o]}
              </option>
            ))}
          </select>
        )}
      </Campo>
      {borrador.ocasion === "otra" && (
        <Campo id="f-ocasion-detalle" etiqueta="¿Qué ocasión?" errores={errores.ocasion_detalle}>
          {(a) => (
            <input
              id="f-ocasion-detalle"
              className="campo__control"
              value={borrador.ocasion_detalle}
              maxLength={LIMITES.ocasionDetalle}
              onChange={(e) => actualizar({ ocasion_detalle: e.target.value })}
              {...a}
            />
          )}
        </Campo>
      )}
      <Campo id="f-quien" etiqueta="Quién regala" obligatorio errores={errores.quien_regala} pista="Firma la dedicatoria.">
        {(a) => (
          <input
            id="f-quien"
            className="campo__control"
            value={borrador.quien_regala}
            maxLength={LIMITES.quienRegala}
            onChange={(e) => actualizar({ quien_regala: e.target.value })}
            {...a}
          />
        )}
      </Campo>
      <Campo
        id="f-mensaje"
        etiqueta="Mensaje para la dedicatoria"
        errores={errores.mensaje_dedicatoria}
        pista={`Lo que quieres decir; el arquitecto lo integra. ${borrador.mensaje_dedicatoria.length}/${LIMITES.mensajeDedicatoria}`}
      >
        {(a) => (
          <textarea
            id="f-mensaje"
            className="campo__control"
            rows={3}
            value={borrador.mensaje_dedicatoria}
            maxLength={LIMITES.mensajeDedicatoria}
            onChange={(e) => actualizar({ mensaje_dedicatoria: e.target.value })}
            {...a}
          />
        )}
      </Campo>
    </>
  );
}

export function PasoTerror({ borrador, actualizar, errores }: PropsPaso) {
  return (
    <>
      <Grupo
        id="g-intensidad"
        leyenda="Intensidad"
        obligatorio
        errores={errores.intensidad}
        pista="Cada nivel tiene una edad mínima. Ninguno admite contenido sexual."
      >
        <div className="intensidades">
          {(Object.keys(INTENSIDADES) as Intensidad[]).map((nivel) => {
            const n = INTENSIDADES[nivel];
            return (
              <label key={nivel} className="opcion-radio">
                <input
                  type="radio"
                  name="intensidad"
                  value={nivel}
                  checked={borrador.intensidad === nivel}
                  onChange={() => actualizar({ intensidad: nivel })}
                />
                <span className="opcion-radio__caja">
                  <span className="opcion-radio__nombre">{ETIQUETA_INTENSIDAD[nivel]}</span>
                  <span className="intensidad__edad">Desde {n.edadMinima} años · {n.publico}</span>
                  <span className="opcion-radio__desc">
                    <strong>Admite:</strong> {n.admite}.
                  </span>
                  <span className="opcion-radio__desc">
                    <strong>No admite:</strong> {n.noAdmite}.
                  </span>
                </span>
              </label>
            );
          })}
        </div>
      </Grupo>
      <Grupo id="g-tono" leyenda="Tono" obligatorio errores={errores.tono}>
        <div className="radios">
          {TONOS.map((t) => (
            <label key={t} className="opcion-radio">
              <input type="radio" name="tono" value={t} checked={borrador.tono === t} onChange={() => actualizar({ tono: t })} />
              <span className="opcion-radio__caja">
                <span className="opcion-radio__nombre">{ETIQUETA_TONO[t][0]}</span>
                <span className="opcion-radio__desc">{ETIQUETA_TONO[t][1]}</span>
              </span>
            </label>
          ))}
        </div>
      </Grupo>
      <Campo id="f-subgenero" etiqueta="Subgénero" errores={errores.subgenero}>
        {(a) => (
          <select
            id="f-subgenero"
            className="campo__control campo__control--medio"
            value={borrador.subgenero}
            onChange={(e) => actualizar({ subgenero: e.target.value as Borrador["subgenero"] })}
            {...a}
          >
            <option value="">Que lo elija el arquitecto</option>
            {SUBGENEROS.map((s) => (
              <option key={s} value={s}>
                {ETIQUETA_SUBGENERO[s]}
              </option>
            ))}
          </select>
        )}
      </Campo>
      <Campo
        id="f-capitulos"
        etiqueta="Capítulos"
        errores={errores.capitulos}
        pista={`De ${LIMITES.capitulos.min} a ${LIMITES.capitulos.max}, de 1.000 a 1.500 palabras cada uno.`}
      >
        {(a) => (
          <input
            id="f-capitulos"
            className="campo__control campo__control--num"
            type="number"
            min={LIMITES.capitulos.min}
            max={LIMITES.capitulos.max}
            value={borrador.capitulos}
            onChange={(e) => actualizar({ capitulos: e.target.value })}
            {...a}
          />
        )}
      </Campo>
      <Campo
        id="f-vetados"
        etiqueta="Términos vetados"
        errores={errores.vetados}
        pista={`Palabras o temas que no pueden aparecer, separados por comas. Hasta ${LIMITES.vetados}.`}
      >
        {(a) => (
          <textarea
            id="f-vetados"
            className="campo__control"
            rows={2}
            value={borrador.vetados}
            onChange={(e) => actualizar({ vetados: e.target.value })}
            {...a}
          />
        )}
      </Campo>
    </>
  );
}
