import { type KeyboardEvent, useEffect, useId, useRef, useState } from "react";
import "./ui.css";

export interface OpcionMenu {
  etiqueta: string;
  alElegir: () => void;
  /** Si viene, la opción se ve pero no se puede elegir, y esto explica por qué. */
  noDisponible?: string;
}

interface Props {
  /** Nombre accesible del botón, por ejemplo «Acciones: La bodega once». */
  etiqueta: string;
  opciones: readonly OpcionMenu[];
  className?: string;
}

/**
 * Botón ⋯ con menú de acciones (RF-FE-TAB-05). Intro o Espacio lo abre, las flechas recorren
 * las opciones, Escape lo cierra y devuelve el foco al botón.
 */
export function MenuAcciones({ etiqueta, opciones, className }: Props) {
  const [abierto, setAbierto] = useState(false);
  const idMenu = useId();
  const boton = useRef<HTMLButtonElement>(null);
  const lista = useRef<HTMLUListElement>(null);

  const elementos = () => Array.from(lista.current?.querySelectorAll<HTMLButtonElement>("[role=menuitem]") ?? []);

  const cerrar = (devolverFoco: boolean) => {
    setAbierto(false);
    if (devolverFoco) boton.current?.focus();
  };

  useEffect(() => {
    if (!abierto) return;
    elementos()[0]?.focus();
    const fuera = (evento: PointerEvent) => {
      const objetivo = evento.target as Node;
      if (!lista.current?.contains(objetivo) && !boton.current?.contains(objetivo)) setAbierto(false);
    };
    document.addEventListener("pointerdown", fuera);
    return () => document.removeEventListener("pointerdown", fuera);
  }, [abierto]);

  const alTeclear = (evento: KeyboardEvent<HTMLUListElement>) => {
    const todos = elementos();
    const actual = todos.indexOf(document.activeElement as HTMLButtonElement);
    const ir = (i: number) => todos[(i + todos.length) % todos.length]?.focus();
    switch (evento.key) {
      case "ArrowDown":
        evento.preventDefault();
        ir(actual + 1);
        break;
      case "ArrowUp":
        evento.preventDefault();
        ir(actual - 1);
        break;
      case "Home":
        evento.preventDefault();
        ir(0);
        break;
      case "End":
        evento.preventDefault();
        ir(todos.length - 1);
        break;
      case "Escape":
        evento.preventDefault();
        cerrar(true);
        break;
      case "Tab":
        cerrar(false);
        break;
    }
  };

  return (
    <div className={`menu ${className ?? ""}`}>
      <button
        ref={boton}
        type="button"
        className="menu__boton"
        aria-label={etiqueta}
        aria-haspopup="menu"
        aria-expanded={abierto}
        aria-controls={abierto ? idMenu : undefined}
        onClick={() => setAbierto((a) => !a)}
      >
        ⋯
      </button>
      {abierto && (
        <ul ref={lista} id={idMenu} className="menu__lista" role="menu" aria-label={etiqueta} onKeyDown={alTeclear}>
          {opciones.map((opcion) => (
            <li key={opcion.etiqueta} role="none">
              <button
                type="button"
                role="menuitem"
                className="menu__opcion"
                aria-disabled={opcion.noDisponible ? true : undefined}
                onClick={() => {
                  if (opcion.noDisponible) return;
                  cerrar(true);
                  opcion.alElegir();
                }}
              >
                <span>{opcion.etiqueta}</span>
                {opcion.noDisponible && <span className="menu__motivo">{opcion.noDisponible}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
