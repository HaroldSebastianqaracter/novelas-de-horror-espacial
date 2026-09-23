/**
 * Pieza ambiental de «Nueva novela» (RF-FE-BRF-06): una estación de anillo dibujada como un
 * plano técnico, girando despacio sobre un campo de estrellas. Decorativa y sin interacción.
 * - `prefers-reduced-motion`: un único fotograma, sin animación.
 * - Pestaña oculta: se detiene.
 * - Sin WebGL: se queda la silueta SVG estática.
 * Los colores salen de los tokens (RF-FE-VIS-01), leídos al montar.
 */
import { useEffect, useRef, useState } from "react";

const token = (nombre: string) => getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();

export default function AmbienteEstacion() {
  const contenedor = useRef<HTMLDivElement>(null);
  const [conWebgl, setConWebgl] = useState(false);

  useEffect(() => {
    const nodo = contenedor.current;
    if (!nodo) return;
    let limpiar: (() => void) | undefined;
    let vivo = true;

    void import("three").then((THREE) => {
      if (!vivo) return;
      let renderer: InstanceType<typeof THREE.WebGLRenderer>;
      try {
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
      } catch {
        return; // Sin WebGL: queda el SVG.
      }

      const escena = new THREE.Scene();
      const camara = new THREE.PerspectiveCamera(38, 1, 0.1, 300);
      camara.position.set(0, 3.2, 17);
      camara.lookAt(0, 0, 0);

      const tinta = new THREE.Color(token("--color-acento"));
      const trazo = new THREE.LineBasicMaterial({ color: tinta, transparent: true, opacity: 0.85 });
      const tenue = new THREE.LineBasicMaterial({ color: tinta, transparent: true, opacity: 0.32 });

      const circulo = (radio: number, z: number) =>
        new THREE.BufferGeometry().setFromPoints(
          Array.from({ length: 97 }, (_, i) => {
            const a = (i / 96) * Math.PI * 2;
            return new THREE.Vector3(Math.cos(a) * radio, Math.sin(a) * radio, z);
          }),
        );
      const aristas = (g: ConstructorParameters<typeof THREE.EdgesGeometry>[0], m: InstanceType<typeof THREE.LineBasicMaterial>) =>
        new THREE.LineSegments(new THREE.EdgesGeometry(g, 1), m);

      // Anillo habitable: dos pares de circunferencias unidas por cuadernas, y radios al núcleo.
      const grupo = new THREE.Group();
      const anillo = new THREE.Group();
      const R1 = 4.0;
      const R2 = 4.7;
      const H = 0.45;
      for (const [r, z] of [[R1, -H], [R1, H], [R2, -H], [R2, H]] as const) anillo.add(new THREE.Line(circulo(r, z), trazo));
      const cuadernas: InstanceType<typeof THREE.Vector3>[] = [];
      for (let i = 0; i < 36; i++) {
        const a = (i / 36) * Math.PI * 2;
        const c = Math.cos(a);
        const s = Math.sin(a);
        cuadernas.push(
          new THREE.Vector3(c * R1, s * R1, -H), new THREE.Vector3(c * R2, s * R2, -H),
          new THREE.Vector3(c * R1, s * R1, H), new THREE.Vector3(c * R2, s * R2, H),
          new THREE.Vector3(c * R2, s * R2, -H), new THREE.Vector3(c * R2, s * R2, H),
        );
      }
      anillo.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(cuadernas), tenue));
      const radios: InstanceType<typeof THREE.Vector3>[] = [];
      for (let i = 0; i < 4; i++) {
        const a = (i / 4) * Math.PI * 2 + Math.PI / 4;
        radios.push(new THREE.Vector3(Math.cos(a) * 0.7, Math.sin(a) * 0.7, 0), new THREE.Vector3(Math.cos(a) * R1, Math.sin(a) * R1, 0));
      }
      anillo.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(radios), trazo));
      grupo.add(anillo);

      // Núcleo, espina, módulos, radiadores y antena: no giran con el anillo.
      const nucleo = aristas(new THREE.CylinderGeometry(0.7, 0.7, 1.6, 12), trazo);
      nucleo.rotation.x = Math.PI / 2;
      grupo.add(nucleo);
      const espina = aristas(new THREE.CylinderGeometry(0.22, 0.22, 11, 6), tenue);
      espina.rotation.x = Math.PI / 2;
      grupo.add(espina);
      [-3.2, -4.4, 3.0].forEach((z, i) => {
        const modulo = aristas(new THREE.BoxGeometry(0.9 - i * 0.15, 0.9 - i * 0.15, 1.0), trazo);
        modulo.position.z = z;
        grupo.add(modulo);
      });
      for (const lado of [-1, 1]) {
        const panel = aristas(new THREE.BoxGeometry(2.8, 0.04, 0.9), tenue);
        panel.position.set(lado * 1.9, 0, -4.4);
        grupo.add(panel);
      }
      const antena = aristas(new THREE.ConeGeometry(0.8, 0.5, 12, 1, true), trazo);
      antena.rotation.x = -Math.PI / 2;
      antena.position.z = 5.8;
      grupo.add(antena);
      grupo.rotation.set(0.55, -0.5, 0.1);
      escena.add(grupo);

      // Estrellas en una cáscara esférica lejana.
      const n = 600;
      const posiciones = new Float32Array(n * 3);
      for (let i = 0; i < n; i++) {
        const r = 45 + Math.random() * 60;
        const t = Math.random() * Math.PI * 2;
        const f = Math.acos(2 * Math.random() - 1);
        posiciones.set([r * Math.sin(f) * Math.cos(t), r * Math.sin(f) * Math.sin(t), r * Math.cos(f)], i * 3);
      }
      const geometriaEstrellas = new THREE.BufferGeometry();
      geometriaEstrellas.setAttribute("position", new THREE.BufferAttribute(posiciones, 3));
      const estrellas = new THREE.Points(
        geometriaEstrellas,
        new THREE.PointsMaterial({ color: new THREE.Color(token("--color-lectura-tenue")), size: 0.2, transparent: true, opacity: 0.5 }),
      );
      escena.add(estrellas);

      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      nodo.appendChild(renderer.domElement);
      setConWebgl(true);

      const ajustar = () => {
        const w = nodo.clientWidth || 1;
        const h = nodo.clientHeight || 1;
        renderer.setSize(w, h, false);
        camara.aspect = w / h;
        camara.updateProjectionMatrix();
        renderer.render(escena, camara);
      };
      const observador = typeof ResizeObserver === "function" ? new ResizeObserver(ajustar) : null;
      observador?.observe(nodo);
      ajustar();

      const movimientoReducido = window.matchMedia("(prefers-reduced-motion: reduce)");
      let cuadro = 0;
      let previo = 0;
      const pintar = (t: number) => {
        cuadro = requestAnimationFrame(pintar);
        const dt = Math.min(64, t - (previo || t));
        previo = t;
        anillo.rotation.z += dt * 0.00008; // una vuelta cada ~80 s
        grupo.rotation.y += dt * 0.000015;
        estrellas.rotation.y += dt * 0.000004;
        renderer.render(escena, camara);
      };
      const arrancar = () => {
        if (!cuadro && !movimientoReducido.matches && !document.hidden) {
          previo = 0;
          cuadro = requestAnimationFrame(pintar);
        }
      };
      const detener = () => {
        cancelAnimationFrame(cuadro);
        cuadro = 0;
        renderer.render(escena, camara);
      };
      const alCambiar = () => (movimientoReducido.matches || document.hidden ? detener() : arrancar());
      movimientoReducido.addEventListener("change", alCambiar);
      document.addEventListener("visibilitychange", alCambiar);
      arrancar();

      limpiar = () => {
        detener();
        observador?.disconnect();
        movimientoReducido.removeEventListener("change", alCambiar);
        document.removeEventListener("visibilitychange", alCambiar);
        escena.traverse((o) => {
          const objeto = o as { geometry?: { dispose(): void }; material?: { dispose(): void } };
          objeto.geometry?.dispose();
          objeto.material?.dispose();
        });
        renderer.dispose();
        renderer.domElement.remove();
      };
    });

    return () => {
      vivo = false;
      limpiar?.();
    };
  }, []);

  return (
    <div className="ambiente" ref={contenedor} data-webgl={conWebgl ? true : undefined}>
      <svg className="ambiente__respaldo" viewBox="0 0 400 500" fill="none" stroke="currentColor">
        <ellipse cx="200" cy="250" rx="150" ry="60" />
        <ellipse cx="200" cy="250" rx="125" ry="48" />
        <line x1="200" y1="120" x2="200" y2="380" />
        <rect x="185" y="230" width="30" height="40" />
      </svg>
    </div>
  );
}
