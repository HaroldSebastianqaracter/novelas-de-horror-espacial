import {
  type Announcements,
  DndContext,
  type DragEndEvent,
  DragOverlay,
  type DragOverEvent,
  type DragStartEvent,
  MouseSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { useQueries, useQuery } from "@tanstack/react-query";
import { type ReactNode, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { consultaEjecucion, consultaNovelas } from "../../compartido/api/consultas";
import { useIntenciones } from "../../compartido/api/intenciones";
import { comoEstadoEjecucion, ESTADOS_ACTIVOS } from "../../compartido/api/reglas";
import { EstadoConsulta } from "../../compartido/ui/EstadoConsulta";
import type { OpcionMenu } from "../../compartido/ui/Menu";
import { accionesDe, type Destino, destinoPara, type IntencionDeTablero } from "./acciones";
import { type Columna, COLUMNAS, type GrupoId, grupoDe } from "./columnas";
import { destinoDe, ETIQUETA_INTENCION, estadoDe, type NovelaEnTablero, Tarjeta, tituloDe } from "./Tarjeta";
import "./TableroGeneral.css";

const reciente = (x: NovelaEnTablero) => x.ejecucion?.actualizado_en ?? x.novela.creado_en;

function agrupar(novelas: NovelaEnTablero[]): Record<GrupoId, NovelaEnTablero[]> {
  const grupos: Record<GrupoId, NovelaEnTablero[]> = {
    espera: [],
    planificando: [],
    escribiendo: [],
    terminada: [],
    atencion: [],
  };
  for (const x of novelas) grupos[grupoDe(estadoDe(x))].push(x);
  for (const g of Object.values(grupos)) g.sort((a, b) => reciente(b).localeCompare(reciente(a)));
  return grupos;
}

const esActiva = (x: NovelaEnTablero) => {
  const estado = comoEstadoEjecucion(estadoDe(x));
  return estado !== null && ESTADOS_ACTIVOS.has(estado);
};

const plural = (n: number, singular: string, varias: string) => (n === 1 ? singular : varias);

/** Tablero general (RF-FE-TAB). */
export function TableroGeneral() {
  const novelas = useQuery(consultaNovelas());
  // El resumen no trae fase ni total: una consulta de ejecución por novela (RF-FE-API-04).
  const ejecuciones = useQueries({ queries: (novelas.data ?? []).map((n) => consultaEjecucion(n.id)) });
  const { pendientes, rechazos, pedir, descartarRechazo } = useIntenciones();
  const navegar = useNavigate();
  const [arrastrada, setArrastrada] = useState<NovelaEnTablero | null>(null);
  const [sobre, setSobre] = useState<GrupoId | null>(null);
  const [errorPedir, setErrorPedir] = useState<string | null>(null);
  // Soltar una tarjeta dispara también un clic sobre su enlace: se descarta (RF-FE-TAB-03).
  const finArrastre = useRef(0);
  const sensores = useSensors(useSensor(MouseSensor, { activationConstraint: { distance: 6 } }));

  const enTablero: NovelaEnTablero[] = (novelas.data ?? []).map((novela, i) => ({
    novela,
    ejecucion: ejecuciones[i]?.data,
  }));
  const grupos = agrupar(enTablero);
  const activa = enTablero.find(esActiva);
  const atencion = grupos.atencion.length;
  const pendienteDe = (novelaId: number) => pendientes.find((p) => p.novelaId === novelaId);
  const hayOtraActiva = (x: NovelaEnTablero) => activa !== undefined && activa.novela.id !== x.novela.id;

  const pedirIntencion = (tipo: IntencionDeTablero, x: NovelaEnTablero) => {
    setErrorPedir(null);
    pedir({ tipo, novela_id: x.novela.id, payload: {} }).catch((e: unknown) =>
      setErrorPedir(`No se pudo pedir «${ETIQUETA_INTENCION[tipo]}» para ${tituloDe(x.novela)}: ${(e as Error).message}`),
    );
  };

  const opcionesDe = (x: NovelaEnTablero): OpcionMenu[] => [
    ...accionesDe(estadoDe(x), hayOtraActiva(x)).map((a) => ({
      etiqueta: ETIQUETA_INTENCION[a.tipo] ?? a.tipo,
      alElegir: () => pedirIntencion(a.tipo, x),
      noDisponible: pendienteDe(x.novela.id) ? "Ya hay una intención en cola para esta novela" : a.noDisponible,
    })),
    { etiqueta: "Abrir", alElegir: () => void navegar(destinoDe(x)) },
  ];

  const tarjeta = (x: NovelaEnTablero) => {
    // Se deja arrastrar aunque la acción no esté disponible: la zona bloqueada explica por qué (RF-FE-TAB-04).
    const arrastrable = !pendienteDe(x.novela.id) && accionesDe(estadoDe(x), hayOtraActiva(x)).length > 0;
    return (
      <TarjetaArrastrable key={x.novela.id} id={x.novela.id} activa={arrastrable} finArrastre={finArrastre}>
        <Tarjeta
          {...x}
          opciones={opcionesDe(x)}
          pendiente={pendienteDe(x.novela.id)}
          rechazo={rechazos[x.novela.id]}
          alDescartarRechazo={() => descartarRechazo(x.novela.id)}
        />
      </TarjetaArrastrable>
    );
  };

  const alEmpezar = ({ active }: DragStartEvent) =>
    setArrastrada(enTablero.find((x) => x.novela.id === active.id) ?? null);

  const alSoltar = ({ over }: DragEndEvent) => {
    finArrastre.current = Date.now();
    const x = arrastrada;
    setArrastrada(null);
    setSobre(null);
    if (!x || !over) return;
    const destino = destinoPara(estadoDe(x), hayOtraActiva(x), over.id as GrupoId);
    if (destino.tipo === "valido") pedirIntencion(destino.intencion, x);
  };

  const destinoDeColumna = (columna: GrupoId): Destino | undefined =>
    arrastrada ? destinoPara(estadoDe(arrastrada), hayOtraActiva(arrastrada), columna) : undefined;

  // Lo que pasaría al soltar, pegado al puntero: la zona puede quedar tapada por la propia tarjeta.
  const destinoSobre = sobre ? destinoDeColumna(sobre) : undefined;

  const anuncios: Announcements = {
    onDragStart: () => `Arrastrando ${arrastrada ? tituloDe(arrastrada.novela) : "la novela"}.`,
    onDragOver: ({ over }) => (over ? `Sobre la columna ${nombreDe(over.id as GrupoId)}.` : "Fuera de las columnas."),
    onDragEnd: ({ over }) => (over ? `Soltada en ${nombreDe(over.id as GrupoId)}.` : "Soltada fuera: no se pide nada."),
    onDragCancel: () => "Arrastre cancelado: no se pide nada.",
  };

  return (
    <section className="pantalla pantalla--tablero" aria-labelledby="titulo-tablero">
      <header className="pantalla__cabecera">
        <div>
          <h1 id="titulo-tablero">Tablero general</h1>
          {novelas.data && (
            <p className="resumen">
              {enTablero.length} {plural(enTablero.length, "novela", "novelas")} · en curso:{" "}
              <strong>{activa ? tituloDe(activa.novela) : "ninguna"}</strong> · {atencion}{" "}
              {plural(atencion, "requiere", "requieren")} atención
            </p>
          )}
        </div>
        <Link className="boton boton--primario" to="/crear">
          <span aria-hidden="true">+</span> Nueva novela
        </Link>
      </header>

      <EstadoConsulta cargando={novelas.isPending} error={novelas.error} reintentar={() => void novelas.refetch()}>
        {enTablero.length === 0 ? (
          <TableroVacio />
        ) : (
          <>
            <p className="ayuda-arrastre">
              Arrastra de <strong>En espera</strong> a <strong>Planificando</strong> para arrancar, y de vuelta a{" "}
              <strong>En espera</strong> para parar. Con teclado o en pantalla táctil, usa el botón ⋯ de cada tarjeta.
              Se genera una novela a la vez.
            </p>
            {errorPedir && (
              <p className="aviso aviso--error" role="alert">
                {errorPedir}
              </p>
            )}
            <DndContext
              sensors={sensores}
              onDragStart={alEmpezar}
              onDragOver={({ over }: DragOverEvent) => setSobre((over?.id as GrupoId | undefined) ?? null)}
              onDragEnd={alSoltar}
              onDragCancel={() => {
                setArrastrada(null);
                setSobre(null);
              }}
              accessibility={{ announcements: anuncios }}
            >
              <CarrilAtencion novelas={grupos.atencion} tarjeta={tarjeta} />
              <div className="tablero" data-arrastrando={arrastrada ? true : undefined}>
                {COLUMNAS.map((columna) => (
                  <ColumnaSoltable
                    key={columna.id}
                    columna={columna}
                    cuantas={grupos[columna.id].length}
                    destino={destinoDeColumna(columna.id)}
                  >
                    {grupos[columna.id].length > 0 ? (
                      grupos[columna.id].map(tarjeta)
                    ) : (
                      <p className="columna__vacio">{columna.vacio}</p>
                    )}
                  </ColumnaSoltable>
                ))}
              </div>
              <DragOverlay dropAnimation={null}>
                {arrastrada && (
                  <div className="fantasma">
                    <Tarjeta {...arrastrada} fantasma />
                    {destinoSobre && destinoSobre.tipo !== "origen" && (
                      <p className="fantasma__destino" data-destino={destinoSobre.tipo}>
                        {destinoSobre.tipo === "valido" ? TEXTO_DESTINO[destinoSobre.intencion] : destinoSobre.motivo}
                      </p>
                    )}
                  </div>
                )}
              </DragOverlay>
            </DndContext>
          </>
        )}
      </EstadoConsulta>
    </section>
  );
}

const nombreDe = (id: GrupoId) => COLUMNAS.find((c) => c.id === id)?.nombre ?? "Requiere atención";

const TEXTO_DESTINO: Record<IntencionDeTablero, string> = {
  arrancar: "Soltar para arrancar",
  parar: "Soltar para parar",
};

interface PropsColumna {
  columna: Columna;
  cuantas: number;
  destino?: Destino;
  children: ReactNode;
}

function ColumnaSoltable({ columna, cuantas, destino, children }: PropsColumna) {
  // Todas las columnas detectan el puntero, también las bloqueadas, para poder explicar por qué;
  // quien decide si soltar pide algo es `alSoltar`.
  const { setNodeRef, isOver } = useDroppable({ id: columna.id });
  const idTitulo = `columna-${columna.id}`;
  return (
    <section
      ref={setNodeRef}
      className="columna"
      data-columna={columna.id}
      data-destino={destino?.tipo}
      data-sobre={isOver ? true : undefined}
      aria-labelledby={idTitulo}
    >
      <header className="columna__cabecera">
        <h2 id={idTitulo}>{columna.nombre}</h2>
        <span className="cuenta" aria-label={`${cuantas} ${plural(cuantas, "novela", "novelas")}`}>
          {cuantas}
        </span>
        <p className="columna__estados">{columna.estados.join(" · ")}</p>
      </header>
      <div className="columna__zona">{children}</div>
      {destino && destino.tipo !== "origen" && (
        <div className="zona-destino" aria-hidden="true">
          <span className="zona-destino__texto">
            {destino.tipo === "valido" ? TEXTO_DESTINO[destino.intencion] : destino.motivo}
          </span>
        </div>
      )}
    </section>
  );
}

function TarjetaArrastrable({
  id,
  activa,
  finArrastre,
  children,
}: {
  id: number;
  activa: boolean;
  finArrastre: { current: number };
  children: ReactNode;
}) {
  // Sin `attributes`: la tarjeta no es un control más para el teclado; su vía es el menú (RF-FE-TAB-05).
  const { setNodeRef, listeners, isDragging } = useDraggable({ id, disabled: !activa });
  return (
    <div
      ref={setNodeRef}
      {...listeners}
      className="arrastrable"
      data-arrastrable={activa}
      data-arrastrando={isDragging ? true : undefined}
      onClickCapture={(evento) => {
        if (Date.now() - finArrastre.current < 300) {
          evento.preventDefault();
          evento.stopPropagation();
        }
      }}
    >
      {children}
    </div>
  );
}

/** Carril de parada y error: siempre visible, nunca escondido dentro de otra columna (RF-FE-TAB-01). */
function CarrilAtencion({
  novelas,
  tarjeta,
}: {
  novelas: NovelaEnTablero[];
  tarjeta: (x: NovelaEnTablero) => ReactNode;
}) {
  const vacio = novelas.length === 0;
  return (
    <section className="carril-atencion" data-vacio={vacio} aria-labelledby="titulo-atencion">
      <header className="carril-atencion__cabecera">
        <h2 id="titulo-atencion">
          <span aria-hidden="true">■</span> Requiere atención{" "}
          <span className="cuenta" aria-label={`${novelas.length} ${plural(novelas.length, "novela", "novelas")}`}>
            {novelas.length}
          </span>
        </h2>
        <p>parada · error: no se arrastran, se abren para decidir</p>
      </header>
      <div className="carril-atencion__zona">
        {vacio ? <p className="carril-atencion__vacio">Sin incidencias. Ninguna ejecución espera decisión.</p> : novelas.map(tarjeta)}
      </div>
    </section>
  );
}

/** Primera vez: qué es esto y por dónde se empieza (RF-FE-TAB-06). */
function TableroVacio() {
  return (
    <div className="vacio">
      <h2>Todavía no hay novelas</h2>
      <p>
        Cada novela nace <strong>En espera</strong>. Al arrancarla, los agentes la planifican y la escriben solos,
        durante horas. Este tablero observa y avisa cuando algo necesita tu decisión.
      </p>
      <ol className="vacio__flujo" aria-label="Recorrido de una novela">
        {COLUMNAS.map((c) => (
          <li key={c.id}>{c.nombre}</li>
        ))}
      </ol>
      <Link className="boton boton--primario" to="/crear">
        Crea la primera
      </Link>
    </div>
  );
}
