/-
Invariantes temporales de una novela de storyMaker (specs/spec-lean.md, RF-LEAN-03).

El generador (`src/backend/orquestador/lean.py`) escribe un fichero con solo DATOS:
eventos con su dia, presencias, nacimientos, muertes y edades declaradas. Este modulo define
los invariantes como proposiciones decidibles, la lista de testigos de cada uno y los lemas que
dicen que la lista esta vacia si y solo si el invariante se cumple (RF-LEAN-04). Asi el fichero
de una novela afirma cada invariante con `decide`, y si alguno falla los testigos dicen que
evento y que personaje lo rompen, sin poder discrepar de la comprobacion.

El tiempo se cuenta en dias desde el comienzo de la historia (spec3, RF3-BIB-08): enteros,
negativos antes del dia 0.
-/

namespace Storymaker

/-- Un evento de la vista `cronologia` con dia. -/
structure Evento where
  id : Nat
  dia : Int
  /-- Orden interno; solo vale si `conOrden`. -/
  orden : Int := 0
  conOrden : Bool := false
  capitulo : Nat := 0
  /-- Antecedente del mundo: sin escena. -/
  previo : Bool := false
  /-- Linea principal: dramatizado, con escena y fuera de una analepsis. -/
  linea : Bool := false
  /-- Su escena es una analepsis. -/
  analepsis : Bool := false
  /-- Mayor dia de la linea principal en las escenas anteriores a la suya, o 0. -/
  presente : Int := 0

/-- Un personaje presente en la escena de un evento, con el dia de ese evento. -/
structure Presencia where
  evento : Nat
  personaje : Nat
  dia : Int

/-- El dia de nacimiento de la vista `personaje_nacimiento` (spec3, RF3-BIB-05). -/
structure Nacimiento where
  personaje : Nat
  dia : Int

/-- La ultima condicion registrada del personaje es `muerto`, el dia de esa escena. -/
structure Muerte where
  personaje : Nat
  dia : Int

/-- Una edad que la prosa afirma (un hecho `edad` con cifras), el dia de su escena. -/
structure EdadDeclarada where
  hecho : Nat
  personaje : Nat
  dia : Int
  edad : Int

structure Datos where
  eventos : List Evento := []
  presencias : List Presencia := []
  nacimientos : List Nacimiento := []
  muertes : List Muerte := []
  edades : List EdadDeclarada := []

/-- La edad en un dia, con la formula de spec3 (RF3-BIB-05): `⌊(dia − nacimiento) / 365⌋`.
La division de `Int` redondea hacia abajo con divisor positivo. -/
def edadEn (nacimiento dia : Int) : Int := (dia - nacimiento) / 365

/-! ## Invariantes -/

/-- Todo personaje presente en un evento ya ha nacido ese dia. -/
abbrev NadieAntesDeNacer (d : Datos) : Prop :=
  ∀ p ∈ d.presencias, ∀ n ∈ d.nacimientos, n.personaje = p.personaje → n.dia ≤ p.dia

/-- Nadie esta presente en un evento de un dia posterior al de su muerte. -/
abbrev NadieTrasMorir (d : Datos) : Prop :=
  ∀ p ∈ d.presencias, ∀ m ∈ d.muertes, m.personaje = p.personaje → p.dia ≤ m.dia

/-- Una edad declarada es la que da el nacimiento ese dia. -/
abbrev EdadCoherente (d : Datos) : Prop :=
  ∀ e ∈ d.edades, ∀ n ∈ d.nacimientos, n.personaje = e.personaje → edadEn n.dia e.dia = e.edad

abbrev AntecedentesAntes (d : Datos) : Prop :=
  ∀ e ∈ d.eventos, e.previo = true → e.dia ≤ 0

abbrev LineaDesdeElInicio (d : Datos) : Prop :=
  ∀ e ∈ d.eventos, e.linea = true → 0 ≤ e.dia

/-- En la linea principal, un orden interno menor o igual no cae en un dia posterior. Con
orden igual, los dos sentidos obligan al mismo dia. -/
abbrev LineaEnOrden (d : Datos) : Prop :=
  ∀ a ∈ d.eventos, ∀ b ∈ d.eventos,
    (a.linea && b.linea && a.conOrden && b.conOrden) = true → a.orden ≤ b.orden → a.dia ≤ b.dia

abbrev AnalepsisEnElPasado (d : Datos) : Prop :=
  ∀ e ∈ d.eventos, e.analepsis = true → e.dia ≤ e.presente

abbrev ElTiempoNoRetrocede (d : Datos) : Prop :=
  AntecedentesAntes d ∧ LineaDesdeElInicio d ∧ LineaEnOrden d ∧ AnalepsisEnElPasado d

/-! ## Testigos -/

/-- Una violacion concreta. `evento` y `otro` son ids de evento; `hecho` el de una edad
declarada; `dia` es lo observado y `limite` lo que el invariante permitia. -/
structure Testigo where
  comprobacion : String
  evento : Nat := 0
  otro : Nat := 0
  personaje : Nat := 0
  hecho : Nat := 0
  dia : Int := 0
  limite : Int := 0

def testigosNacer (d : Datos) : List Testigo :=
  d.presencias.flatMap fun p =>
    (d.nacimientos.filter fun n => n.personaje = p.personaje ∧ p.dia < n.dia).map fun n =>
      { comprobacion := "lean_nadie_antes_de_nacer", evento := p.evento,
        personaje := p.personaje, dia := p.dia, limite := n.dia }

def testigosMorir (d : Datos) : List Testigo :=
  d.presencias.flatMap fun p =>
    (d.muertes.filter fun m => m.personaje = p.personaje ∧ m.dia < p.dia).map fun m =>
      { comprobacion := "lean_nadie_tras_morir", evento := p.evento,
        personaje := p.personaje, dia := p.dia, limite := m.dia }

def testigosEdad (d : Datos) : List Testigo :=
  d.edades.flatMap fun e =>
    (d.nacimientos.filter fun n => n.personaje = e.personaje ∧ edadEn n.dia e.dia ≠ e.edad).map
      fun n =>
        { comprobacion := "lean_edad_coherente", hecho := e.hecho, personaje := e.personaje,
          dia := e.edad, limite := edadEn n.dia e.dia }

def testigosAntecedentes (d : Datos) : List Testigo :=
  (d.eventos.filter fun e => e.previo = true ∧ 0 < e.dia).map fun e =>
    { comprobacion := "lean_el_tiempo_no_retrocede", evento := e.id, dia := e.dia, limite := 0 }

def testigosInicio (d : Datos) : List Testigo :=
  (d.eventos.filter fun e => e.linea = true ∧ e.dia < 0).map fun e =>
    { comprobacion := "lean_el_tiempo_no_retrocede", evento := e.id, dia := e.dia, limite := 0 }

def testigosOrden (d : Datos) : List Testigo :=
  d.eventos.flatMap fun a =>
    (d.eventos.filter fun b =>
        (a.linea && b.linea && a.conOrden && b.conOrden) = true ∧ a.orden ≤ b.orden ∧
          b.dia < a.dia).map fun b =>
      { comprobacion := "lean_el_tiempo_no_retrocede", evento := a.id, otro := b.id,
        dia := a.dia, limite := b.dia }

def testigosAnalepsis (d : Datos) : List Testigo :=
  (d.eventos.filter fun e => e.analepsis = true ∧ e.presente < e.dia).map fun e =>
    { comprobacion := "lean_el_tiempo_no_retrocede", evento := e.id, dia := e.dia,
      limite := e.presente }

def testigosTiempo (d : Datos) : List Testigo :=
  testigosAntecedentes d ++ testigosInicio d ++ testigosOrden d ++ testigosAnalepsis d

def testigos (d : Datos) : List Testigo :=
  testigosNacer d ++ testigosMorir d ++ testigosEdad d ++ testigosTiempo d

/-! ## Lemas generales (RF-LEAN-04): sin testigos si y solo si se cumple -/

theorem testigosNacer_vacio (d : Datos) : testigosNacer d = [] ↔ NadieAntesDeNacer d := by
  simp [testigosNacer, NadieAntesDeNacer]

theorem testigosMorir_vacio (d : Datos) : testigosMorir d = [] ↔ NadieTrasMorir d := by
  simp [testigosMorir, NadieTrasMorir]

theorem testigosEdad_vacio (d : Datos) : testigosEdad d = [] ↔ EdadCoherente d := by
  simp [testigosEdad, EdadCoherente]

theorem testigosTiempo_vacio (d : Datos) : testigosTiempo d = [] ↔ ElTiempoNoRetrocede d := by
  simp [testigosTiempo, testigosAntecedentes, testigosInicio, testigosOrden, testigosAnalepsis,
    ElTiempoNoRetrocede, AntecedentesAntes, LineaDesdeElInicio, LineaEnOrden,
    AnalepsisEnElPasado]

/-- La edad avanza un año exacto cada 365 dias, para cualquier nacimiento. -/
theorem edadEn_mas_un_anio (n d : Int) : edadEn n (d + 365) = edadEn n d + 1 := by
  unfold edadEn
  rw [show d + 365 - n = (d - n) + 1 * 365 by omega, Int.add_mul_ediv_right _ _ (by decide)]

/-! ## Informe -/

def Testigo.linea (t : Testigo) : String :=
  s!"TESTIGO {t.comprobacion} evento={t.evento} otro={t.otro} personaje={t.personaje} " ++
    s!"hecho={t.hecho} dia={t.dia} limite={t.limite}"

/-- Imprime un testigo por linea; el ejecutor de Python los lee (RF-LEAN-05). -/
def informe (d : Datos) : IO Unit := do
  for t in testigos d do
    IO.println t.linea

end Storymaker
