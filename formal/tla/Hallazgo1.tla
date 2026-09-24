------------------------------- MODULE Hallazgo1 -------------------------------
(***************************************************************************)
(* La maquina ANTERIOR a la fase 2 de spec2 (el padre del commit 68d9e7e),  *)
(* para reproducir el hallazgo 1 de la auditoria: resolver una parada de    *)
(* estructura acababa en `completada` sin capitulos.                        *)
(*                                                                         *)
(* Solo modela lo que hace falta para el hallazgo: la derivacion de avanzar *)
(* por el ESTADO, la tabla de transiciones de entonces y la resolucion de   *)
(* paradas sin tipo. Sin caidas, sin parar y sin versiones (no existian).   *)
(* El capitulo es un solo paso: cierra o abre parada de continuidad.        *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets

CONSTANTS N, MaxFallos

Caps == 1..N
Completadas == {"completada", "completada_con_avisos"}
NINGUNA == "ninguna"
INVALIDA == "INVALIDA"

\* orquestador/estados.py en 68d9e7e^: la parada se resuelve siempre hacia generando.
Transiciones == {
    <<"configurada", "arrancar", "planificando">>,
    <<"planificando", "puerta_1_ok", "escaletando">>,
    <<"escaletando", "puerta_2_ok", "generando">>,
    <<"planificando", "parar", "detenida">>,
    <<"escaletando", "parar", "detenida">>,
    <<"generando", "parar", "detenida">>,
    <<"detenida", "arrancar_planificacion", "planificando">>,
    <<"detenida", "arrancar_escaleta", "escaletando">>,
    <<"detenida", "arrancar_generacion", "generando">>,
    <<"error", "arrancar_planificacion", "planificando">>,
    <<"error", "arrancar_escaleta", "escaletando">>,
    <<"error", "arrancar_generacion", "generando">>,
    <<"planificando", "conflicto", "parada">>,
    <<"escaletando", "conflicto", "parada">>,
    <<"generando", "conflicto", "parada">>,
    <<"parada", "resolver", "generando">>,
    <<"generando", "terminado_limpio", "completada">>,
    <<"generando", "terminado_con_avisos", "completada_con_avisos">>,
    <<"planificando", "error", "error">>,
    <<"escaletando", "error", "error">>,
    <<"generando", "error", "error">>,
    <<"parada", "error", "error">>
}
\* `relanzar` se admitia desde cualquier estado salvo configurada, tambien desde parada.
AdmitenRelanzar == {"planificando", "escaletando", "generando", "parada", "detenida",
                    "completada", "completada_con_avisos", "error"}

Siguiente(desde, suceso) ==
    IF suceso = "relanzar"
    THEN IF desde \in AdmitenRelanzar THEN "generando" ELSE INVALIDA
    ELSE IF \E t \in Transiciones : t[1] = desde /\ t[2] = suceso
         THEN (CHOOSE t \in Transiciones : t[1] = desde /\ t[2] = suceso)[3]
         ELSE INVALIDA

Meta == [arrancar_planificacion |-> "planificando",
         arrancar_escaleta      |-> "escaletando",
         arrancar_generacion    |-> "generando"]

Asegurar(e, suceso) ==
    LET d == Meta[suceso] IN
    IF e = d THEN e
    ELSE IF e = "configurada"
         THEN IF d = "planificando" THEN "planificando"
              ELSE Siguiente("planificando",
                             IF d = "escaletando" THEN "puerta_1_ok" ELSE "puerta_2_ok")
    ELSE Siguiente(e, suceso)

MarcaError(e) == IF Siguiente(e, "error") = INVALIDA THEN e ELSE "error"

VARIABLES estado, tipoParada, capParada, corriendo, pc,
          planificado, escaleta, p1, p2, escIntento, cap, fallos

vars == <<estado, tipoParada, capParada, corriendo, pc, planificado, escaleta, p1, p2,
          escIntento, cap, fallos>>

Pendiente == [i \in Caps |-> "pendiente"]
Total == IF escaleta THEN N ELSE 0
Completados == {i \in Caps : cap[i] = "completado"}
MaxCompletado ==
    IF Completados = {} THEN 0
    ELSE CHOOSE m \in Completados : \A j \in Completados : j <= m
PuedeFallar == fallos < MaxFallos
Acabar == corriendo' = FALSE /\ pc' = "reposo"
Corre(x) == corriendo /\ pc = x

FallarRun == estado' = MarcaError(estado) /\ Acabar

EntrarFase(suceso, destino) ==
    LET e2 == Asegurar(estado, suceso) IN
    IF e2 = INVALIDA THEN FallarRun ELSE estado' = e2 /\ pc' = destino /\ UNCHANGED corriendo

AbrirParada(tipo, c) ==
    estado' = Siguiente(estado, "conflicto") /\ tipoParada' = tipo /\ capParada' = c /\ Acabar

\* avanzar de spec1: planifica solo si el ESTADO dice que toca y falta alguna fase.
Derivar ==
    /\ Corre("inicio")
    /\ IF estado \in {"configurada", "detenida", "error", "planificando"} /\ ~planificado
       THEN EntrarFase("arrancar_planificacion", "plan_agentes")
       ELSE pc' = "chk_esc" /\ UNCHANGED <<estado, corriendo>>
    /\ UNCHANGED <<tipoParada, capParada, planificado, escaleta, p1, p2, escIntento, cap, fallos>>

PlanAgentes ==
    /\ Corre("plan_agentes")
    /\ planificado' = TRUE /\ pc' = "plan_p1"
    /\ UNCHANGED <<estado, tipoParada, capParada, corriendo, escaleta, p1, p2, escIntento,
                   cap, fallos>>

PlanP1 ==
    /\ Corre("plan_p1")
    /\ \/ /\ p1' = TRUE /\ estado' = Siguiente(estado, "puerta_1_ok") /\ pc' = "chk_esc"
          /\ UNCHANGED <<tipoParada, capParada, corriendo, fallos>>
       \/ /\ PuedeFallar /\ fallos' = fallos + 1 /\ p1' = FALSE
          /\ AbrirParada("estructura", 0)
    /\ UNCHANGED <<planificado, escaleta, p2, escIntento, cap>>

\* avanzar de spec1: la escaleta, otra vez segun el estado.
ChkEsc ==
    /\ Corre("chk_esc")
    /\ IF estado \in {"escaletando", "detenida", "error"}
       THEN IF ~escaleta
            THEN EntrarFase("arrancar_escaleta", "esc_agente") /\ escIntento' = 1
            ELSE EntrarFase("arrancar_generacion", "chk_gen") /\ UNCHANGED escIntento
       ELSE pc' = "chk_gen" /\ UNCHANGED <<estado, corriendo, escIntento>>
    /\ UNCHANGED <<tipoParada, capParada, planificado, escaleta, p1, p2, cap, fallos>>

EscAgente ==
    /\ Corre("esc_agente")
    /\ IF escaleta THEN UNCHANGED <<escaleta, cap>> ELSE escaleta' = TRUE /\ cap' = Pendiente
    /\ pc' = "esc_p2"
    /\ UNCHANGED <<estado, tipoParada, capParada, corriendo, planificado, p1, p2, escIntento,
                   fallos>>

\* escaletar de spec1: la segunda vez, la parada se abre SIN borrar la escaleta (hallazgo 2).
EscP2 ==
    /\ Corre("esc_p2")
    /\ \/ /\ p2' = TRUE /\ estado' = Siguiente(estado, "puerta_2_ok") /\ pc' = "chk_gen"
          /\ UNCHANGED <<tipoParada, capParada, corriendo, escaleta, cap, escIntento, fallos>>
       \/ /\ PuedeFallar /\ fallos' = fallos + 1 /\ p2' = FALSE
          /\ IF escIntento = 2
             THEN AbrirParada("escaleta", 0) /\ UNCHANGED <<escaleta, cap, escIntento>>
             ELSE /\ escaleta' = FALSE /\ cap' = Pendiente /\ escIntento' = 2
                  /\ pc' = "esc_agente"
                  /\ UNCHANGED <<estado, tipoParada, capParada, corriendo>>
    /\ UNCHANGED <<planificado, p1>>

ChkGen ==
    /\ Corre("chk_gen")
    /\ IF estado # "generando"
       THEN EntrarFase("arrancar_generacion", "caps")
       ELSE pc' = "caps" /\ UNCHANGED <<estado, corriendo>>
    /\ UNCHANGED <<tipoParada, capParada, planificado, escaleta, p1, p2, escIntento, cap, fallos>>

\* El bucle y generar_capitulo de spec1: sin guardarrail de puertas.
Bucle ==
    /\ Corre("caps")
    /\ LET s == MaxCompletado + 1 IN
       IF s <= Total
       THEN \/ /\ cap' = [cap EXCEPT ![s] = "completado"]
               /\ UNCHANGED <<estado, tipoParada, capParada, corriendo, pc, fallos>>
            \/ /\ PuedeFallar /\ fallos' = fallos + 1
               /\ AbrirParada("continuidad", s) /\ UNCHANGED cap
       ELSE pc' = "p5" /\ UNCHANGED <<estado, tipoParada, capParada, corriendo, cap, fallos>>
    /\ UNCHANGED <<planificado, escaleta, p1, p2, escIntento>>

P5 ==
    /\ Corre("p5")
    /\ \E suceso \in {"terminado_limpio", "terminado_con_avisos"} :
          estado' = Siguiente(estado, suceso)
    /\ Acabar
    /\ UNCHANGED <<tipoParada, capParada, planificado, escaleta, p1, p2, escIntento, cap, fallos>>

\* worker._arrancar de spec1: solo rechaza una parada abierta.
Arrancar ==
    /\ ~corriendo /\ estado # "parada" /\ estado \notin Completadas
    /\ corriendo' = TRUE /\ pc' = "inicio"
    /\ UNCHANGED <<estado, tipoParada, capParada, planificado, escaleta, p1, p2, escIntento,
                   cap, fallos>>

\* worker._resolver_parada de spec1: relanzar o aceptar_retcon sobre CUALQUIER parada, con
\* fallo.relanzar, que revierte desde d y deja la ejecucion en generando.
Resolver ==
    /\ ~corriendo /\ estado = "parada"
    /\ \E d \in 1..(MaxCompletado + 1) :
          cap' = [i \in Caps |-> IF i >= d THEN "pendiente" ELSE cap[i]]
    /\ estado' = Siguiente(estado, "relanzar")
    /\ tipoParada' = NINGUNA /\ capParada' = 0
    /\ corriendo' = TRUE /\ pc' = "inicio"
    /\ UNCHANGED <<planificado, escaleta, p1, p2, escIntento, fallos>>

Next == Derivar \/ PlanAgentes \/ PlanP1 \/ ChkEsc \/ EscAgente \/ EscP2 \/ ChkGen
        \/ Bucle \/ P5 \/ Arrancar \/ Resolver

Init ==
    /\ estado = "configurada" /\ tipoParada = NINGUNA /\ capParada = 0
    /\ corriendo = FALSE /\ pc = "reposo"
    /\ planificado = FALSE /\ escaleta = FALSE /\ p1 = FALSE /\ p2 = FALSE
    /\ escIntento = 1 /\ cap = Pendiente /\ fallos = 0

Spec == Init /\ [][Next]_vars

\* La misma propiedad que StoryMaker.tla: una novela completada es una novela entera con las
\* puertas 1 y 2 vigentes.
CompletadaConNovela ==
    estado \in Completadas =>
        /\ escaleta /\ p1 /\ p2
        /\ \A i \in Caps : cap[i] = "completado"

=============================================================================
