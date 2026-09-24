import { act, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Astronauta } from "./Astronauta";

const conMovimiento = (reducir: boolean) =>
  vi.stubGlobal("matchMedia", (q: string) => ({ matches: reducir && q.includes("reduce"), media: q }) as MediaQueryList);

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  localStorage.clear();
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

  it("con «reducir movimiento», es la imagen quieta", () => {
    conMovimiento(true);
    const { container } = render(<Astronauta />);
    expect(sprite(container)).toBeNull();
    expect(container.querySelector("img.astronauta__estatico")).toBeInTheDocument();
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
    act(() => vi.advanceTimersByTime(60_000));
    expect(sprite(container)).toHaveAttribute("data-animacion", "dormir");
    act(() => void window.dispatchEvent(new Event("keydown")));
    expect(sprite(container)).toHaveAttribute("data-animacion", "asomarse");
  });

  it("al pulsarlo se esconde, y sigue escondido al volver", () => {
    conMovimiento(false);
    const primero = render(<Astronauta />);
    fireEvent.click(primero.container.querySelector(".astronauta") as HTMLElement);
    expect(primero.container.querySelector(".astronauta-pista")).toBeNull();
    primero.unmount();
    expect(render(<Astronauta />).container.querySelector(".astronauta-pista")).toBeNull();
  });
});
