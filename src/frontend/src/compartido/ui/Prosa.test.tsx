import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { compararPalabras } from "../../funcionalidades/lectura/comparar";
import { ConEnfasis, tramosDeEnfasis, trozosConEnfasis } from "./Prosa";

const html = (texto: string) => render(<p><ConEnfasis texto={texto} /></p>).container.querySelector("p")?.innerHTML;

/** La comparación pintada como en CapituloLectura: `<del>` y `<ins>` con la cursiva dentro. */
function comparar(antes: string, despues: string) {
  const trozos = compararPalabras(antes, despues);
  const { container } = render(
    <p>
      {trozosConEnfasis(trozos, (t, contenido, k) =>
        t.tipo === "nuevo" ? <ins key={k}>{contenido}</ins> : t.tipo === "quitado" ? <del key={k}>{contenido}</del> : <span key={k}>{contenido}</span>,
      )}
    </p>,
  );
  const p = container.querySelector("p") as HTMLElement;
  const leer = (quitar: string) => {
    const copia = p.cloneNode(true) as HTMLElement;
    copia.querySelectorAll(quitar).forEach((e) => e.remove());
    return { texto: copia.textContent, cursiva: [...copia.querySelectorAll("em")].map((e) => e.textContent).join("") };
  };
  // Lo que se lee de la versión nueva (sin lo quitado) y de la anterior (sin lo añadido).
  return { html: p.innerHTML, despues: leer("del"), antes: leer("ins") };
}

describe("la cursiva de la prosa (RF-FE-LEE-09)", () => {
  it("lo que va entre asteriscos sale en cursiva y sin ellos", () => {
    const { container } = render(
      <p>
        <ConEnfasis texto="La voz volvió: *Tu pulso es de 131.* Ella no contestó. *Sellado final.*" />
      </p>,
    );
    expect([...container.querySelectorAll("em")].map((e) => e.textContent)).toEqual(["Tu pulso es de 131.", "Sellado final."]);
    expect(container.textContent).toBe("La voz volvió: Tu pulso es de 131. Ella no contestó. Sellado final.");
  });

  it("solo cuenta la marca bien formada: el resto de asteriscos es del texto", () => {
    expect(html("Nota al pie* sin pareja")).toBe("Nota al pie* sin pareja");
    expect(html("5 * 3 * 2 = 30")).toBe("5 * 3 * 2 = 30");
    expect(html("**negrita** y a ** b")).toBe("**negrita** y a ** b");
    expect(html("x *a* y *b")).toBe("x <em>a</em> y *b");
    expect(tramosDeEnfasis("Sin cursivas")).toEqual([{ texto: "Sin cursivas", cursiva: false }]);
  });

  it("en la comparación, la cursiva cruza trozos iguales", () => {
    const r = comparar("Dijo: *Sellado completado.* Y calló.", "Dijo: *Sellado final completado.* Y calló.");
    expect(r.despues).toEqual({ texto: "Dijo: Sellado final completado. Y calló.", cursiva: "Sellado final completado." });
    expect(r.html).toContain("<ins><em>final");
  });

  it("en la comparación, un cambio pegado al asterisco no lo deja a la vista ni invierte la cursiva", () => {
    const a = comparar("La voz: *Tu pulso es de 131.* Ella calla.", "La voz: *Tu pulso es de 140.* Ella calla.");
    expect(a.html).not.toContain("*");
    expect(a.despues).toEqual({ texto: "La voz: Tu pulso es de 140. Ella calla.", cursiva: "Tu pulso es de 140." });
    expect(a.antes).toEqual({ texto: "La voz: Tu pulso es de 131. Ella calla.", cursiva: "Tu pulso es de 131." });

    // Renombrar a quien abre una cursiva y cierra otra.
    const b = comparar("*Toby, sal.* Luego: *ven, Toby.* Fin.", "*Nala, sal.* Luego: *ven, Nala.* Fin.");
    expect(b.html).not.toContain("*");
    expect(b.despues.texto).toBe("Nala, sal. Luego: ven, Nala. Fin.");
    expect(b.despues.cursiva).toBe("Nala, sal.ven, Nala.");

    // La cursiva cambia de extensión.
    const c = comparar("*Hola mundo* al fin", "*Hola* mundo al fin");
    expect(c.html).not.toContain("*");
    expect(c.despues).toEqual({ texto: "Hola mundo al fin", cursiva: "Hola" });
    // El espacio es un trozo igual y va con las marcas de después: en la lectura de antes queda en redonda.
    expect(c.antes.cursiva).toBe("Holamundo");
  });
});
