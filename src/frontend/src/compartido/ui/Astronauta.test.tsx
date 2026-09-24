import { act, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Astronauta, volverAMostrarAstronauta } from "./Astronauta";

/** Simula `matchMedia`; devuelve con qué cambiar «reducir movimiento» en vivo. */
function conMovimiento(reducir: boolean) {
  const oyentes = new Set<() => void>();
  let activo = reducir;
  vi.stubGlobal("matchMedia", (q: string) => ({
    get matches() {
      return activo && q.includes("reduce");
    },
    media: q,
    addEventListener: (_: string, f: () => void) => oyentes.add(f),
    removeEventListener: (_: string, f: () => void) => oyentes.delete(f),
  }));
  return (nuevo: boolean) => {
    activo = nuevo;
    act(() => oyentes.forEach((f) => f()));
  };
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
  volverAMostrarAstronauta();
});

const sprite = (c: HTMLElement) => c.querySelector(".astronauta__sprite") as HTMLElement;

describe("el astronauta", () => {
  it("es decorativo: fuera del árbol de accesibilidad y sin foco", () => {
    conMovimiento(false);
    const { container } = render(<Astronauta />);
    const pista = container.querySelector(".astronauta-pista") as HTMLElement;
    expect(pista).toHaveAttribute("aria-hidden", "true");
    expect(pista.querySelector("[tabindex], button, a")).toBeNull();
    expect(sprite(container)).toHaveAttribute("data-animacion", "idle");
  });

  it("con «reducir movimiento», es la imagen quieta, también si se activa con la página abierta", () => {
    const cambiar = conMovimiento(true);
    const { container } = render(<Astronauta />);
    expect(sprite(container)).toBeNull();
    expect(container.querySelector("img.astronauta__estatico")).toBeInTheDocument();
    cambiar(false);
    expect(sprite(container)).toBeInTheDocument();
    cambiar(true);
    expect(sprite(container)).toBeNull();
  });

  it("pasea hasta su destino y, si la pista se estrecha, se queda dentro y deja de andar", () => {
    vi.useFakeTimers();
    vi.spyOn(Math, "random").mockReturnValue(0.99);
    conMovimiento(false);
    const { container } = render(<Astronauta />);
    const pista = container.querySelector(".astronauta-pista") as HTMLElement;
    let ancho = 1000;
    Object.defineProperty(pista, "clientWidth", { get: () => ancho });
    act(() => vi.advanceTimersByTime(3500));
    expect(sprite(container)).toHaveAttribute("data-animacion", "andar");
    expect(sprite(container)).not.toHaveAttribute("data-sentido");
    act(() => vi.advanceTimersByTime(4000));
    ancho = 196; // útil: 196 - 96 = 100 px
    act(() => vi.advanceTimersByTime(10_000));
    expect(sprite(container)).not.toHaveAttribute("data-animacion", "andar");
    expect((container.querySelector(".astronauta") as HTMLElement).style.transform).toBe("translateX(100px)");
  });

  it("saluda al pasarle el ratón, y se duerme tras un minuto sin actividad", () => {
    vi.useFakeTimers();
    conMovimiento(false);
    const { container } = render(<Astronauta modo="asomarse" />);
    expect(sprite(container)).toHaveAttribute("data-animacion", "asomarse");
    fireEvent.pointerEnter(container.querySelector(".astronauta") as HTMLElement);
    expect(sprite(container)).toHaveAttribute("data-animacion", "saludar");
    act(() => vi.advanceTimersByTime(1500));
    expect(sprite(container)).toHaveAttribute("data-animacion", "asomarse");
    // El minuto cuenta desde el último gesto.
    act(() => void window.dispatchEvent(new Event("pointermove")));
    act(() => vi.advanceTimersByTime(59_000));
    expect(sprite(container)).toHaveAttribute("data-animacion", "asomarse");
    act(() => vi.advanceTimersByTime(1_000));
    expect(sprite(container)).toHaveAttribute("data-animacion", "dormir");
    act(() => void window.dispatchEvent(new Event("keydown")));
    expect(sprite(container)).toHaveAttribute("data-animacion", "asomarse");
  });

  it("al pulsarlo se esconde en todas las pantallas hasta recargar, sin guardarlo", () => {
    conMovimiento(false);
    const primero = render(<Astronauta />);
    fireEvent.click(primero.container.querySelector(".astronauta") as HTMLElement);
    expect(primero.container.querySelector(".astronauta-pista")).toBeNull();
    primero.unmount();
    // Otra pantalla, sin recargar: sigue escondido.
    expect(render(<Astronauta modo="asomarse" />).container.querySelector(".astronauta-pista")).toBeNull();
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it("al esconder uno se esconden los que hay a la vista (el tablero vacío tiene dos)", () => {
    conMovimiento(false);
    const { container } = render(
      <>
        <Astronauta />
        <Astronauta modo="asomarse" />
      </>,
    );
    expect(container.querySelectorAll(".astronauta-pista")).toHaveLength(2);
    fireEvent.click(container.querySelector(".astronauta") as HTMLElement);
    expect(container.querySelectorAll(".astronauta-pista")).toHaveLength(0);
  });
});
