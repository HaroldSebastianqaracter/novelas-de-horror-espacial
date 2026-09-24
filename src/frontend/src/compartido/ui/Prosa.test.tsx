import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConEnfasis, tramosDeEnfasis, trozosConEnfasis } from "./Prosa";

describe("la cursiva de la prosa (RF-FE-LEE-09)", () => {
  it("lo que va entre asteriscos sale en cursiva y sin ellos", () => {
    const { container } = render(
      <p>
        <ConEnfasis texto="La voz volvió: *Tu pulso es de 131.* Ella no contestó. *Sellado final.*" />
      </p>,
    );
    expect(container.querySelectorAll("em")).toHaveLength(2);
    expect(container.querySelector("em")).toHaveTextContent("Tu pulso es de 131.");
    expect(container).toHaveTextContent("La voz volvió: Tu pulso es de 131. Ella no contestó. Sellado final.");
    expect(container.textContent).not.toContain("*");
  });

  it("un asterisco suelto es del texto y no se toca", () => {
    expect(tramosDeEnfasis("Nota al pie* sin pareja")).toEqual([{ texto: "Nota al pie* sin pareja", cursiva: false }]);
    expect(tramosDeEnfasis("Sin cursivas")).toEqual([{ texto: "Sin cursivas", cursiva: false }]);
  });

  it("en la comparación, la cursiva sigue de un trozo al siguiente", () => {
    const trozos = [
      { tipo: "igual", texto: "Dijo: *Sellado " },
      { tipo: "nuevo", texto: "final" },
      { tipo: "igual", texto: " completado.* Y calló." },
    ];
    const { container } = render(
      <p>{trozosConEnfasis(trozos, (t, contenido, k) => (t.tipo === "nuevo" ? <ins key={k}>{contenido}</ins> : <span key={k}>{contenido}</span>))}</p>,
    );
    expect([...container.querySelectorAll("em")].map((e) => e.textContent)).toEqual(["Sellado ", "final", " completado."]);
    expect(container.querySelector("ins em")).toHaveTextContent("final");
    expect(container.textContent).toBe("Dijo: Sellado final completado. Y calló.");
  });
});
