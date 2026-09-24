import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import estatico from "../imagenes/astronauta/astronauta-estatico.svg";
import "./Astronauta.css";

type Animacion = "idle" | "andar" | "saludar" | "flotar" | "asomarse" | "dormir";

/**
 * `pasear` recorre su pista alternando andar, reposo y flotar; `asomarse` saca el casco una vez
 * (pantallas vacías); `flotar` flota en el sitio (cargas).
 */
type Modo = "pasear" | "asomarse" | "flotar";

const TILE = 96; // 32 px del sprite a ×3
const VELOCIDAD = TILE / 32 / 80; // 1 px del sprite cada 80 ms, en px de pantalla por ms
const SALUDO_MS = 2 * 720; // dos ciclos de «saludar»
const SUENO_MS = 60_000;

// Escondido hasta recargar la página: vale para todas las pantallas y todos los astronautas a la vez,
// y no se guarda en ningún almacenamiento.
let escondido = false;
const suscritos = new Set<() => void>();
const avisar = () => suscritos.forEach((f) => f());
const suscribirEscondido = (f: () => void) => {
  suscritos.add(f);
  return () => void suscritos.delete(f);
};
const esconderTodos = () => {
  escondido = true;
  avisar();
};
export const volverAMostrarAstronauta = () => {
  escondido = false;
  avisar();
};

// «Reducir movimiento», en vivo. Sin matchMedia (jsdom) cuenta como activo: la imagen quieta.
const CONSULTA = "(prefers-reduced-motion: reduce)";
const suscribirMovimiento = (f: () => void) => {
  if (typeof matchMedia !== "function") return () => {};
  const mq = matchMedia(CONSULTA);
  mq.addEventListener?.("change", f);
  return () => mq.removeEventListener?.("change", f);
};
const reducirMovimiento = () => typeof matchMedia !== "function" || matchMedia(CONSULTA).matches;

const entre = (min: number, max: number) => min + Math.random() * (max - min);

/**
 * El astronauta pixel art que acompaña la portada, el índice, la consola y las pantallas vacías o de
 * carga. Es decorativo: no entra en el árbol de accesibilidad, no recibe foco y su pista no captura el
 * ratón, así que no tapa controles. Al pulsarlo se esconde hasta recargar la página.
 */
export function Astronauta({ modo = "pasear", className }: { modo?: Modo; className?: string }) {
  const oculto = useSyncExternalStore(suscribirEscondido, () => escondido);
  const quieto = useSyncExternalStore(suscribirMovimiento, reducirMovimiento);
  const [base, setBase] = useState<Animacion>(modo === "pasear" ? "idle" : modo);
  const [izquierda, setIzquierda] = useState(false);
  const [saludando, setSaludando] = useState(false);
  const [dormido, setDormido] = useState(false);
  const pista = useRef<HTMLDivElement>(null);
  const figura = useRef<HTMLSpanElement>(null);
  const parado = useRef(false);
  parado.current = saludando || dormido;

  // Paseo: la posición se escribe directamente en el estilo en cada frame; React solo se entera de
  // los cambios de animación y de sentido.
  useEffect(() => {
    if (quieto || oculto || modo !== "pasear") return;
    let x = 0;
    let destino = 0;
    let animacion: Animacion = "idle";
    let hasta = performance.now() + entre(1500, 3000);
    let anterior = performance.now();
    let frame = 0;
    setBase("idle");
    const paso = (ahora: number) => {
      const dt = Math.min(ahora - anterior, 100);
      anterior = ahora;
      // Si la pista se estrecha, el astronauta y su destino se quedan dentro.
      const ancho = Math.max((pista.current?.clientWidth ?? 0) - TILE, 0);
      x = Math.min(x, ancho);
      destino = Math.min(destino, ancho);
      if (!parado.current) {
        if (animacion === "andar") {
          const falta = destino - x;
          x += Math.sign(falta) * Math.min(Math.abs(falta), VELOCIDAD * dt);
          if (x === destino) {
            // Al llegar, reposa o flota un rato (ciclos enteros de «flotar»: 4 × 320 ms).
            animacion = Math.random() < 0.6 ? "idle" : "flotar";
            hasta = ahora + (animacion === "idle" ? entre(2500, 6000) : 1280 * Math.ceil(entre(2, 4)));
            setBase(animacion);
          }
        } else if (ahora >= hasta && ancho > 0) {
          destino = Math.round(entre(0, ancho));
          if (Math.abs(destino - x) > TILE / 2) {
            animacion = "andar";
            setIzquierda(destino < x);
            setBase("andar");
          } else {
            hasta = ahora + entre(1500, 3000);
          }
        }
      }
      if (figura.current) figura.current.style.transform = `translateX(${x}px)`;
      frame = requestAnimationFrame(paso);
    };
    frame = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(frame);
  }, [quieto, oculto, modo]);

  // Tras un minuto sin actividad, se duerme; cualquier gesto lo despierta.
  useEffect(() => {
    if (quieto || oculto) return;
    let temporizador = window.setTimeout(() => setDormido(true), SUENO_MS);
    const actividad = () => {
      setDormido(false);
      window.clearTimeout(temporizador);
      temporizador = window.setTimeout(() => setDormido(true), SUENO_MS);
    };
    const eventos = ["pointermove", "pointerdown", "keydown", "scroll", "wheel"] as const;
    for (const e of eventos) window.addEventListener(e, actividad, { passive: true });
    return () => {
      window.clearTimeout(temporizador);
      for (const e of eventos) window.removeEventListener(e, actividad);
    };
  }, [quieto, oculto]);

  useEffect(() => {
    if (!saludando) return;
    const t = window.setTimeout(() => setSaludando(false), SALUDO_MS);
    return () => window.clearTimeout(t);
  }, [saludando]);

  if (oculto) return null;

  const animacion: Animacion = dormido ? "dormir" : saludando ? "saludar" : base;

  return (
    <div ref={pista} className={`astronauta-pista astronauta-pista--${modo}${className ? ` ${className}` : ""}`} aria-hidden="true">
      <span
        ref={figura}
        className="astronauta"
        title="Pulsa para esconderlo"
        onClick={esconderTodos}
        onPointerEnter={() => !quieto && setSaludando(true)}
      >
        {quieto ? (
          <img className="astronauta__estatico" src={estatico} alt="" width={TILE} height={TILE} draggable={false} />
        ) : (
          <span className="astronauta__sprite" data-animacion={animacion} data-sentido={izquierda ? "izquierda" : undefined} />
        )}
      </span>
    </div>
  );
}
