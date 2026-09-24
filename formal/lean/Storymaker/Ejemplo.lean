/-
Novela 1: generado por src/backend/orquestador/lean.py.
No editar a mano: se regenera desde la story bible (specs/spec-lean.md).

Eventos con dia: 7. Sin dia, no comprobados: 0.
Muertes en una escena sin dia, no comprobadas: 0.
Edades declaradas en una escena sin dia, no comprobadas: 0.
-/
import Storymaker.Cronologia

open Storymaker

namespace Ejemplo

def datos : Datos where
  eventos := [
    { id := 1, dia := -240, orden := -1, conOrden := true, previo := true },  -- La estacion deja de responder.
    { id := 2, dia := 1, orden := 11, conOrden := true, capitulo := 1, linea := true },  -- Sucesos de la escena 1
    { id := 3, dia := 1, orden := 12, conOrden := true, capitulo := 1, linea := true, presente := 1 },  -- Sucesos de la escena 2
    { id := 4, dia := 2, orden := 21, conOrden := true, capitulo := 2, linea := true, presente := 1 },  -- Sucesos de la escena 1
    { id := 5, dia := 2, orden := 22, conOrden := true, capitulo := 2, linea := true, presente := 2 },  -- Sucesos de la escena 2
    { id := 6, dia := 3, orden := 31, conOrden := true, capitulo := 3, linea := true, presente := 2 },  -- Sucesos de la escena 1
    { id := 7, dia := 3, orden := 32, conOrden := true, capitulo := 3, linea := true, presente := 3 }  -- Sucesos de la escena 2
  ]
  presencias := [
    { evento := 2, personaje := 1, dia := 1 },  -- Idris
    { evento := 2, personaje := 2, dia := 1 },  -- Vaan
    { evento := 3, personaje := 1, dia := 1 },  -- Idris
    { evento := 3, personaje := 2, dia := 1 },  -- Vaan
    { evento := 4, personaje := 1, dia := 2 },  -- Idris
    { evento := 4, personaje := 2, dia := 2 },  -- Vaan
    { evento := 5, personaje := 1, dia := 2 },  -- Idris
    { evento := 5, personaje := 2, dia := 2 },  -- Vaan
    { evento := 6, personaje := 1, dia := 3 },  -- Idris
    { evento := 6, personaje := 2, dia := 3 },  -- Vaan
    { evento := 7, personaje := 1, dia := 3 },  -- Idris
    { evento := 7, personaje := 2, dia := 3 }  -- Vaan
  ]
  nacimientos := [
    { personaje := 1, dia := -14052 },  -- Idris
    { personaje := 2, dia := -19162 },  -- Vaan
    { personaje := 3, dia := -10767 }  -- Reyes
  ]
  muertes := [
    { personaje := 3, dia := 3 }  -- Reyes
  ]
  edades := []

#eval informe datos

theorem nadie_antes_de_nacer : NadieAntesDeNacer datos := by decide +kernel
theorem nadie_tras_morir : NadieTrasMorir datos := by decide +kernel
theorem edad_coherente : EdadCoherente datos := by decide +kernel
theorem el_tiempo_no_retrocede : ElTiempoNoRetrocede datos := by decide +kernel

end Ejemplo
