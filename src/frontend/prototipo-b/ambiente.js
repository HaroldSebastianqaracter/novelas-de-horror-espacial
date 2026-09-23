/* ==========================================================================
   novelasv2 · pieza ambiental (Three.js) para "Crear novela" · PROPUESTA B
   Una estación de anillo dibujada en tinta azul, como un plano técnico, girando despacio sobre un campo de
   estrellas. Decorativa: aria-hidden, sin interacción.
   - prefers-reduced-motion: se dibuja un único fotograma, sin animación.
   - Pestaña oculta o pantalla abandonada: se detiene y libera la GPU.
   - Sin WebGL o sin Three.js (CDN caído): no hace nada; queda visible la silueta SVG estática.
   ========================================================================== */
(function () {
  "use strict";

  let actual = null;

  function colorToken(nombre, porDefecto) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
    return v || porDefecto;
  }

  function lineasCirculo(THREE, radio, z, segmentos) {
    const pts = [];
    for (let i = 0; i <= segmentos; i++) {
      const a = (i / segmentos) * Math.PI * 2;
      pts.push(new THREE.Vector3(Math.cos(a) * radio, Math.sin(a) * radio, z));
    }
    return new THREE.BufferGeometry().setFromPoints(pts);
  }

  function aristas(THREE, geometria, material) {
    return new THREE.LineSegments(new THREE.EdgesGeometry(geometria, 1), material);
  }

  function construirEstacion(THREE, ambar) {
    const grupo = new THREE.Group();
    const trazo = new THREE.LineBasicMaterial({ color: ambar, transparent: true, opacity: 0.85 });
    const tenue = new THREE.LineBasicMaterial({ color: ambar, transparent: true, opacity: 0.32 });

    // Anillo habitable: dos pares de circunferencias unidas por cuadernas
    const anillo = new THREE.Group();
    const R1 = 4.0, R2 = 4.7, H = 0.45;
    [[R1, -H], [R1, H], [R2, -H], [R2, H]].forEach(([r, z]) => anillo.add(new THREE.Line(lineasCirculo(THREE, r, z, 96), trazo)));
    const cuadernas = [];
    for (let i = 0; i < 36; i++) {
      const a = (i / 36) * Math.PI * 2, c = Math.cos(a), s = Math.sin(a);
      cuadernas.push(
        new THREE.Vector3(c * R1, s * R1, -H), new THREE.Vector3(c * R2, s * R2, -H),
        new THREE.Vector3(c * R1, s * R1, H), new THREE.Vector3(c * R2, s * R2, H),
        new THREE.Vector3(c * R2, s * R2, -H), new THREE.Vector3(c * R2, s * R2, H));
    }
    anillo.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(cuadernas), tenue));
    // Radios hacia el núcleo
    const radios = [];
    for (let i = 0; i < 4; i++) {
      const a = (i / 4) * Math.PI * 2 + Math.PI / 4;
      radios.push(new THREE.Vector3(Math.cos(a) * 0.7, Math.sin(a) * 0.7, 0), new THREE.Vector3(Math.cos(a) * R1, Math.sin(a) * R1, 0));
    }
    anillo.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(radios), trazo));
    grupo.add(anillo);

    // Núcleo y espina (no giran con el anillo)
    const nucleo = aristas(THREE, new THREE.CylinderGeometry(0.7, 0.7, 1.6, 12), trazo);
    nucleo.rotation.x = Math.PI / 2;
    grupo.add(nucleo);
    const espina = aristas(THREE, new THREE.CylinderGeometry(0.22, 0.22, 11, 6), tenue);
    espina.rotation.x = Math.PI / 2;
    grupo.add(espina);
    // Módulos a lo largo de la espina
    [-3.2, -4.4, 3.0].forEach((z, i) => {
      const m = aristas(THREE, new THREE.BoxGeometry(0.9 - i * 0.15, 0.9 - i * 0.15, 1.0), trazo);
      m.position.z = z; grupo.add(m);
    });
    // Paneles radiadores
    [-1, 1].forEach((lado) => {
      const p = aristas(THREE, new THREE.BoxGeometry(2.8, 0.04, 0.9), tenue);
      p.position.set(lado * 1.9, 0, -4.4); grupo.add(p);
    });
    // Antena parabólica
    const antena = aristas(THREE, new THREE.ConeGeometry(0.8, 0.5, 12, 1, true), trazo);
    antena.rotation.x = -Math.PI / 2; antena.position.z = 5.8;
    grupo.add(antena);

    return { grupo, anillo };
  }

  function construirEstrellas(THREE, color) {
    const n = 600, pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const r = 45 + Math.random() * 60;
      const t = Math.random() * Math.PI * 2, f = Math.acos(2 * Math.random() - 1);
      pos[i * 3] = r * Math.sin(f) * Math.cos(t);
      pos[i * 3 + 1] = r * Math.sin(f) * Math.sin(t);
      pos[i * 3 + 2] = r * Math.cos(f);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    return new THREE.Points(g, new THREE.PointsMaterial({ color, size: 0.2, sizeAttenuation: true, transparent: true, opacity: 0.5 }));
  }

  function montar(contenedor) {
    desmontar();
    if (!contenedor) return;
    const THREE = window.THREE;
    if (!THREE) { contenedor.dataset.sinWebgl = "true"; return; }

    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
    } catch (e) { contenedor.dataset.sinWebgl = "true"; return; }

    const consulta = window.matchMedia("(prefers-reduced-motion: reduce)");
    const escena = new THREE.Scene();
    const camara = new THREE.PerspectiveCamera(38, 1, 0.1, 300);
    camara.position.set(0, 3.2, 17);
    camara.lookAt(0, 0, 0);

    const ambar = new THREE.Color(colorToken("--color-acento", "#ffb000"));
    const estrellaColor = new THREE.Color(colorToken("--color-lectura-tenue", "#a89c86"));
    const { grupo, anillo } = construirEstacion(THREE, ambar);
    grupo.rotation.set(0.55, -0.5, 0.1);
    escena.add(grupo);
    const estrellas = construirEstrellas(THREE, estrellaColor);
    escena.add(estrellas);

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    contenedor.appendChild(renderer.domElement);
    contenedor.dataset.webgl = "true";

    function ajustar() {
      const w = contenedor.clientWidth || 1, h = contenedor.clientHeight || 1;
      renderer.setSize(w, h, false);
      camara.aspect = w / h;
      camara.updateProjectionMatrix();
      renderer.render(escena, camara);
    }
    const ro = new ResizeObserver(ajustar);
    ro.observe(contenedor);
    ajustar();

    let raf = 0, previo = 0;
    function cuadro(t) {
      raf = requestAnimationFrame(cuadro);
      const dt = Math.min(64, t - (previo || t)); previo = t;
      anillo.rotation.z += dt * 0.00008;      // una vuelta cada ~80 s
      grupo.rotation.y += dt * 0.000015;
      estrellas.rotation.y += dt * 0.000004;
      renderer.render(escena, camara);
    }
    function arrancar() { if (!raf && !consulta.matches && !document.hidden) { previo = 0; raf = requestAnimationFrame(cuadro); } }
    function detener() { cancelAnimationFrame(raf); raf = 0; renderer.render(escena, camara); }
    const alCambiarMovimiento = () => (consulta.matches ? detener() : arrancar());
    const alCambiarVisibilidad = () => (document.hidden ? detener() : arrancar());
    consulta.addEventListener ? consulta.addEventListener("change", alCambiarMovimiento) : consulta.addListener(alCambiarMovimiento);
    document.addEventListener("visibilitychange", alCambiarVisibilidad);
    arrancar();

    actual = function limpiar() {
      detener();
      ro.disconnect();
      consulta.removeEventListener ? consulta.removeEventListener("change", alCambiarMovimiento) : consulta.removeListener(alCambiarMovimiento);
      document.removeEventListener("visibilitychange", alCambiarVisibilidad);
      escena.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); });
      renderer.dispose();
      if (renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement);
      delete contenedor.dataset.webgl;
    };
  }

  function desmontar() { if (actual) { actual(); actual = null; } }

  window.Ambiente = { montar, desmontar };
})();
