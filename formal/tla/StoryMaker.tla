------------------------------- MODULE StoryMaker -------------------------------
(***************************************************************************)
(* La maquina de estados de la generacion de una novela (specs/spec-tla.md). *)
(*                                                                         *)
(* Modela el worker y el orquestador tal como estan en el codigo:           *)
(*   - orquestador/estados.py    las tablas TRANSICIONES y RESOLUCIONES,    *)
(*   - orquestador/pipeline.py   avanzar, planificar, escaletar y           *)
(*                               generar_capitulo, paso a paso,             *)
(*   - orquestador/fallo.py      paradas, relanzar, rehacer y reversion,    *)
(*   - orquestador/versiones.py  publicar,                                  *)
(*   - worker.py                 intenciones, caida y recuperacion.         *)
(*                                                                         *)
(* Cada accion es una transaccion del codigo, o un tramo entre dos: las     *)
(* llamadas al agente caen fuera de las transacciones. El modelo no ve el   *)
(* contenido de las puertas ni el de la prosa. Una puerta es un resultado   *)
(* no determinista, y lo que se comprueba es el ORDEN que impone el         *)
(* orquestador.                                                            *)
(*                                                                         *)
(* El cambio del lector (bloque 8) se modela como lo disena specs/spec3.md, *)
(* seccion 3.8, antes de que exista en el backend. Queda detras de          *)
(* ConCambioDelLector.                                                     *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets, Sequences

CONSTANTS
    N,                     \* capitulos de la escaleta
    MaxIntentos,           \* config.MAX_INTENTOS_CAPITULO (3 en el codigo)
    MaxFallos,             \* fallos que el entorno puede inyectar en toda la historia
    MaxRegeneraciones,     \* veces que el autor rehace una novela ya completada
    ConCambioDelLector,    \* si existe el cambio del lector (spec3, RF3-CAM-06)
    CambioRevalidaPuertas, \* TRUE: el paso final del cambio evalua otra vez las puertas 1
                           \* y 2 (spec3, RF3-CAM-11). FALSE: el diseno anterior, que TLC
                           \* refuto (CambioSinRevalidar.cfg)
    FallosDePuertaAcotados,\* FALSE: puertas y agentes pueden fallar sin limite (solo la
                           \* caida y el parar siguen contando contra MaxFallos)
    MaxReinicios,          \* veces que el autor relanza una novela que le espera. Con
                           \* fallos acotados no limita nada: cada reinicio necesita un fallo
    PresupuestoRevierteEnLaParada,
                           \* FALSE: el codigo de hoy. La parada de presupuesto del tramo 3
                           \* se confirma y el finally revierte despues, en otra transaccion.
                           \* TRUE: las dos cosas en la misma, como la parada de escaleta
    RecuperarRevierteEnParada
                           \* FALSE: el codigo de hoy. recuperar solo revierte ejecuciones
                           \* activas. TRUE: tambien revierte lo posterior al ultimo
                           \* completado en una ejecucion en parada, sin cambiarle el estado

ASSUME /\ N \in Nat \ {0}
       /\ MaxIntentos \in Nat \ {0}
       /\ MaxFallos \in Nat
       /\ MaxRegeneraciones \in Nat
       /\ ConCambioDelLector \in BOOLEAN
       /\ CambioRevalidaPuertas \in BOOLEAN
       /\ FallosDePuertaAcotados \in BOOLEAN
       /\ MaxReinicios \in Nat
       /\ PresupuestoRevierteEnLaParada \in BOOLEAN
       /\ RecuperarRevierteEnParada \in BOOLEAN

Caps == 1..N
Activos == {"planificando", "escaletando", "generando"}
Completadas == {"completada", "completada_con_avisos"}
Reposo == Completadas \cup {"parada", "detenida", "error"}
NINGUNA == "ninguna"
INVALIDA == "INVALIDA"

(***************************************************************************)
(* orquestador/estados.py. comprobar_tablas.py verifica que estas dos      *)
(* tablas son las del codigo, fila a fila.                                  *)
(***************************************************************************)
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
    <<"generando", "terminado_limpio", "completada">>,
    <<"generando", "terminado_con_avisos", "completada_con_avisos">>,
    <<"planificando", "error", "error">>,
    <<"escaletando", "error", "error">>,
    <<"generando", "error", "error">>,
    <<"parada", "error", "error">>
}

Resoluciones == {
    <<"estructura", "rehacer", "planificando">>,
    <<"escaleta", "rehacer", "escaletando">>,
    <<"continuidad", "aceptar_retcon", "generando">>,
    <<"continuidad", "dar_por_sabido", "generando">>,
    <<"continuidad", "relanzar", "generando">>,
    <<"oficio", "relanzar", "generando">>,
    <<"presupuesto", "relanzar", "generando">>
}

\* spec3, RF3-CAM-06: las dos que anade el cambio del lector. Aun no estan en estados.py.
TransicionesDelLector == {
    <<"completada", "cambio_lector", "generando">>,
    <<"completada_con_avisos", "cambio_lector", "generando">>
}

TransicionesModelo ==
    Transiciones \cup (IF ConCambioDelLector THEN TransicionesDelLector ELSE {})

AccionesDeParada == {t[2] : t \in Resoluciones}
AdmitenRelanzar == {"detenida", "completada", "completada_con_avisos", "error"}
AdmitenArrancar == {"configurada", "detenida", "error"}

\* estados.siguiente: el destino, o INVALIDA donde el codigo lanza TransicionInvalida.
Siguiente(desde, suceso, tipo) ==
    IF desde = "parada" /\ suceso \in AccionesDeParada
    THEN IF \E t \in Resoluciones : t[1] = tipo /\ t[2] = suceso
         THEN (CHOOSE t \in Resoluciones : t[1] = tipo /\ t[2] = suceso)[3]
         ELSE INVALIDA
    ELSE IF suceso = "relanzar"
    THEN IF desde \in AdmitenRelanzar THEN "generando" ELSE INVALIDA
    ELSE IF \E t \in TransicionesModelo : t[1] = desde /\ t[2] = suceso
         THEN (CHOOSE t \in TransicionesModelo : t[1] = desde /\ t[2] = suceso)[3]
         ELSE INVALIDA

Meta == [arrancar_planificacion |-> "planificando",
         arrancar_escaleta      |-> "escaletando",
         arrancar_generacion    |-> "generando"]

\* pipeline._asegurar_activa. Si da INVALIDA, su transaccion revierte entera.
Asegurar(e, suceso) ==
    LET d == Meta[suceso] IN
    IF e = d THEN e
    ELSE IF e = "configurada"
         THEN IF d = "planificando" THEN "planificando"
              ELSE Siguiente("planificando",
                             IF d = "escaletando" THEN "puerta_1_ok" ELSE "puerta_2_ok",
                             NINGUNA)
    ELSE Siguiente(e, suceso, NINGUNA)

\* worker._marcar_error: si "error" no es una transicion valida, el fallo se traga y el
\* estado se queda como estaba.
MarcaError(e) == IF Siguiente(e, "error", NINGUNA) = INVALIDA THEN e ELSE "error"

VARIABLES
    estado,          \* ejecucion.estado
    tipoParada,      \* tipo de la parada abierta, o NINGUNA
    capParada,       \* capitulo de la parada abierta (0 si no tiene)
    retcon,          \* la parada senala un hecho que revocar (fallo.hechos_a_revocar)
    sabido,          \* la parada tiene un conocimiento que dar por sabido
    vivo,            \* el proceso del worker existe
    corriendo,       \* hay un pipeline.avanzar en curso
    pc,              \* por donde va avanzar
    planificado,     \* estan las cuatro fases de planificacion (_fase_ya_hecha)
    escaleta,        \* hay capitulos (total_capitulos > 0)
    p1, p2,          \* vigencia.puerta_vigente(1) y (2)
    escIntento,      \* intento de escaletar (1 o 2)
    cur,             \* capitulo que se esta generando
    intento,         \* intento de ese capitulo
    cap,             \* estado de cada capitulo: pendiente, a_medias o completado
    rev,             \* cuantas veces se ha reescrito el texto vigente de cada capitulo
    aprobado,        \* variable fantasma: el texto vigente del capitulo paso las puertas 3
                     \* y 4. Solo la pone a TRUE la rama que las pasa de verdad
    versiones,       \* novela_version: secuencia de instantaneas publicadas
    cambio,          \* cambio_lector.estado: ninguno, reescribiendo, aplicado, fallido,
                     \* interrumpido
    tipoCambio,      \* renombrar o cambiar_hecho
    alcance,         \* capitulos que el cambio reescribe (RF3-CAM-05)
    pendLector,      \* los del alcance que aun no pasaron la puerta 4 en la simulacion
    lectorIntento,   \* intento del capitulo que se corrige
    revBase,         \* rev al empezar el cambio
    lenBase,         \* versiones publicadas al empezar el cambio
    pararPendiente,  \* hay una intencion 'parar' en la cola
    fallos,          \* fallos inyectados hasta ahora
    regeneraciones,  \* regeneraciones pedidas sobre una novela completada
    reinicios,       \* veces que el autor relanzo una novela parada, detenida o en error
    invalida         \* algun paso lanzo TransicionInvalida o PuertasNoVigentes

paradaVars == <<tipoParada, capParada, retcon, sabido>>
grafoVars == <<planificado, escaleta, p1, p2, cap, rev, aprobado>>
bucleVars == <<escIntento, cur, intento>>
lectorVars == <<cambio, tipoCambio, alcance, pendLector, lectorIntento, revBase, lenBase>>
entornoVars == <<pararPendiente, fallos, regeneraciones, reinicios>>
vars == <<estado, paradaVars, vivo, corriendo, pc, grafoVars, bucleVars, versiones,
          lectorVars, entornoVars, invalida>>

Pendiente == [i \in Caps |-> "pendiente"]
Total == IF escaleta THEN N ELSE 0
Completados == {i \in Caps : cap[i] = "completado"}
Min(S) == CHOOSE m \in S : \A j \in S : m <= j
MaxCompletado ==
    IF Completados = {} THEN 0
    ELSE CHOOSE m \in Completados : \A j \in Completados : j <= m

\* fallo.revertir_grafo(desde): todo capitulo >= desde vuelve a planificado.
RevertirDesde(d) == [i \in Caps |-> IF i >= d THEN "pendiente" ELSE cap[i]]

\* Todo capitulo que deja de estar completado pierde la aprobacion de su texto.
Aprobar == aprobado' = [i \in Caps |-> aprobado[i] /\ cap'[i] = "completado"]

PuedeFallar == fallos < MaxFallos
Fallar == fallos' = fallos + 1
\* Una puerta que falla o un agente que devuelve basura. Con FallosDePuertaAcotados = FALSE
\* pueden repetirse para siempre: lo que acota una ejecucion son los limites de reintentos.
FallaPuerta ==
    IF FallosDePuertaAcotados THEN PuedeFallar /\ Fallar ELSE UNCHANGED fallos

\* versiones.publicar: una instantanea del texto vigente, si difiere de la ultima.
Instantanea(r, a) ==
    [caps  |-> [i \in Caps |-> IF cap[i] = "completado" THEN r[i] ELSE 0],
     total |-> Cardinality(Completados),
     ok    |-> \A i \in Completados : a[i],
     p1    |-> p1,
     p2    |-> p2]
PublicarCon(r, a) ==
    versiones' = IF Len(versiones) > 0 /\ versiones[Len(versiones)].caps = Instantanea(r, a).caps
                 THEN versiones
                 ELSE Append(versiones, Instantanea(r, a))

(***************************************************************************)
(* Finales de una ejecucion de avanzar                                      *)
(***************************************************************************)
Acabar == corriendo' = FALSE /\ pc' = "reposo"

\* Una excepcion que sale de avanzar: worker._correr la registra con _marcar_error.
FallarRun == estado' = MarcaError(estado) /\ Acabar /\ UNCHANGED invalida

\* TransicionInvalida o PuertasNoVigentes: el orquestador derivo mal lo que tocaba.
FallarPorInvalida == estado' = MarcaError(estado) /\ invalida' = TRUE /\ Acabar

\* except Detenido en _avanzar: transicion "parar".
DetenerRun ==
    LET e2 == Siguiente(estado, "parar", NINGUNA) IN
    /\ IF e2 = INVALIDA
       THEN estado' = MarcaError(estado) /\ invalida' = TRUE
       ELSE estado' = e2 /\ UNCHANGED invalida
    /\ Acabar

\* pipeline._abrir_parada: la parada y la transicion "conflicto" en una transaccion.
\* `sigue` es por donde continua avanzar despues de confirmarla: "reposo" si la ejecucion
\* acaba ahi (Parado sube hasta _avanzar), o el paso que aun queda en el codigo.
AbrirParadaY(tipo, c, sigue) ==
    LET e2 == Siguiente(estado, "conflicto", NINGUNA) IN
    IF e2 = INVALIDA
    THEN FallarPorInvalida /\ UNCHANGED paradaVars
    ELSE /\ estado' = "parada" /\ tipoParada' = tipo /\ capParada' = c
         /\ IF tipo = "continuidad"
            THEN retcon' \in BOOLEAN /\ sabido' \in BOOLEAN
            ELSE retcon' = FALSE /\ sabido' = FALSE
         /\ IF sigue = "reposo" THEN Acabar ELSE pc' = sigue /\ UNCHANGED corriendo
         /\ UNCHANGED invalida

AbrirParada(tipo, c) == AbrirParadaY(tipo, c, "reposo")

\* Entrar en una fase: _asegurar_activa y seguir en `destino`.
EntrarFase(suceso, destino) ==
    LET e2 == Asegurar(estado, suceso) IN
    IF e2 = INVALIDA
    THEN FallarPorInvalida
    ELSE estado' = e2 /\ pc' = destino /\ UNCHANGED <<corriendo, invalida>>

Corre(x) == vivo /\ corriendo /\ pc = x

(***************************************************************************)
(* El sistema: los pasos de avanzar                                         *)
(***************************************************************************)

\* _avanzar deriva del grafo que toca (RF2-PIPE-00), no del estado.
Derivar ==
    /\ Corre("inicio")
    /\ IF ~planificado \/ ~p1
       THEN EntrarFase("arrancar_planificacion", "plan_agentes")
       ELSE pc' = "chk_esc" /\ UNCHANGED <<estado, corriendo, invalida>>
    /\ UNCHANGED <<paradaVars, vivo, grafoVars, bucleVars, versiones, lectorVars, entornoVars>>

\* planificar: arquitecto, mundo, elenco y estructura (los que falten).
PlanAgentes ==
    /\ Corre("plan_agentes")
    /\ IF planificado
       THEN pc' = "plan_p1" /\ UNCHANGED <<estado, corriendo, planificado, fallos, invalida>>
       ELSE \/ /\ planificado' = TRUE /\ pc' = "plan_p1"
               /\ UNCHANGED <<estado, corriendo, fallos, invalida>>
            \/ /\ FallaPuerta /\ FallarRun
               /\ UNCHANGED planificado
            \/ /\ pararPendiente /\ DetenerRun
               /\ UNCHANGED <<planificado, fallos>>
    /\ UNCHANGED <<paradaVars, vivo, escaleta, p1, p2, cap, rev, aprobado, bucleVars,
                   versiones, lectorVars, pararPendiente, regeneraciones,
                   reinicios>>

\* planificar: puerta 1. Si falla, parada de estructura.
PlanP1 ==
    /\ Corre("plan_p1")
    /\ \/ /\ p1' = TRUE
          /\ LET e2 == Siguiente(estado, "puerta_1_ok", NINGUNA) IN
             IF e2 = INVALIDA
             THEN FallarPorInvalida
             ELSE estado' = e2 /\ pc' = "chk_esc" /\ UNCHANGED <<corriendo, invalida>>
          /\ UNCHANGED <<paradaVars, fallos>>
       \/ /\ FallaPuerta /\ p1' = FALSE
          /\ AbrirParada("estructura", 0)
    /\ UNCHANGED <<vivo, planificado, escaleta, p2, cap, rev, aprobado, bucleVars,
                   versiones, lectorVars, pararPendiente, regeneraciones,
                   reinicios>>

\* _avanzar: sin escaleta o sin puerta 2 vigente, escaletar.
ChkEsc ==
    /\ Corre("chk_esc")
    /\ IF ~escaleta \/ ~p2
       THEN EntrarFase("arrancar_escaleta", "esc_agente") /\ escIntento' = 1
       ELSE pc' = "chk_gen" /\ UNCHANGED <<estado, corriendo, invalida, escIntento>>
    /\ UNCHANGED <<paradaVars, vivo, grafoVars, cur, intento, versiones, lectorVars,
                   entornoVars>>

\* escaletar: el agente escribe la escaleta si no la hay.
EscAgente ==
    /\ Corre("esc_agente")
    /\ IF escaleta
       THEN pc' = "esc_p2" /\ UNCHANGED <<estado, corriendo, escaleta, cap, fallos, invalida>>
       ELSE \/ /\ escaleta' = TRUE /\ cap' = Pendiente /\ pc' = "esc_p2"
               /\ UNCHANGED <<estado, corriendo, fallos, invalida>>
            \/ /\ FallaPuerta /\ FallarRun
               /\ UNCHANGED <<escaleta, cap>>
            \/ /\ pararPendiente /\ DetenerRun
               /\ UNCHANGED <<escaleta, cap, fallos>>
    /\ Aprobar
    /\ UNCHANGED <<paradaVars, vivo, planificado, p1, p2, rev, bucleVars, versiones,
                   lectorVars, pararPendiente, regeneraciones,
                   reinicios>>

\* escaletar: puerta 2. El primer fallo borra la escaleta y repite; el segundo la borra en
\* la misma transaccion que abre la parada (RF2-FALLO-03).
EscP2 ==
    /\ Corre("esc_p2")
    /\ \/ /\ p2' = TRUE
          /\ LET e2 == Siguiente(estado, "puerta_2_ok", NINGUNA) IN
             IF e2 = INVALIDA
             THEN FallarPorInvalida
             ELSE estado' = e2 /\ pc' = "chk_gen" /\ UNCHANGED <<corriendo, invalida>>
          /\ UNCHANGED <<paradaVars, escaleta, cap, escIntento, fallos>>
       \/ /\ FallaPuerta /\ p2' = FALSE
          /\ escaleta' = FALSE /\ cap' = Pendiente
          /\ IF escIntento = 2
             THEN AbrirParada("escaleta", 0) /\ UNCHANGED escIntento
             ELSE /\ escIntento' = 2 /\ pc' = "esc_agente"
                  /\ UNCHANGED <<estado, corriendo, invalida, paradaVars>>
    /\ Aprobar
    /\ UNCHANGED <<vivo, planificado, p1, rev, cur, intento, versiones, lectorVars,
                   pararPendiente, regeneraciones,
                   reinicios>>

\* _avanzar: _asegurar_activa("arrancar_generacion") antes del bucle.
ChkGen ==
    /\ Corre("chk_gen")
    /\ EntrarFase("arrancar_generacion", "caps")
    /\ UNCHANGED <<paradaVars, vivo, grafoVars, bucleVars, versiones, lectorVars, entornoVars>>

\* El bucle de _avanzar (siguiente = ultimo_capitulo_completado + 1, que es un MAX) y la
\* entrada de generar_capitulo, con su guardarrail (RF2-PIPE-00b).
Bucle ==
    /\ Corre("caps")
    /\ LET s == MaxCompletado + 1 IN
       IF s <= Total
       THEN IF ~p1 \/ ~p2
            THEN FallarPorInvalida /\ UNCHANGED <<cur, intento>>
            ELSE EntrarFase("arrancar_generacion", "tramo12") /\ cur' = s /\ intento' = 1
       ELSE pc' = "p5" /\ UNCHANGED <<estado, corriendo, invalida, cur, intento>>
    /\ UNCHANGED <<paradaVars, vivo, grafoVars, escIntento, versiones, lectorVars,
                   entornoVars>>

\* generar_capitulo, tramos 1 y 2: redaccion y extraccion fuera de transaccion; texto,
\* hechos y puerta 3 en una sola. Si la puerta 3 falla, esa transaccion revierte entera.
Tramo12 ==
    /\ Corre("tramo12")
    /\ \/ /\ cap' = [cap EXCEPT ![cur] = "a_medias"] /\ pc' = "tramo3"
          /\ UNCHANGED <<estado, corriendo, invalida, paradaVars, fallos>>
       \/ /\ FallaPuerta /\ AbrirParada("presupuesto", cur) /\ UNCHANGED cap
       \/ /\ FallaPuerta /\ AbrirParada("continuidad", cur) /\ UNCHANGED cap
       \/ /\ FallaPuerta /\ FallarRun /\ UNCHANGED <<cap, paradaVars>>
       \/ /\ pararPendiente /\ DetenerRun /\ UNCHANGED <<cap, paradaVars, fallos>>
    /\ Aprobar
    /\ UNCHANGED <<vivo, planificado, escaleta, p1, p2, rev, bucleVars, versiones,
                   lectorVars, pararPendiente, regeneraciones,
                   reinicios>>

\* generar_capitulo, tramo 3: oficio. Si pasa, _cerrar_capitulo. Si falla, se revierte y se
\* reintenta hasta MaxIntentos; cualquier otra salida revierte en el finally.
Tramo3 ==
    /\ Corre("tramo3")
    /\ \/ /\ cap' = [cap EXCEPT ![cur] = "completado"]
          /\ rev' = [rev EXCEPT ![cur] = rev[cur] + 1]
          /\ aprobado' = [aprobado EXCEPT ![cur] = TRUE]
          /\ pc' = "caps"
          /\ UNCHANGED <<estado, corriendo, invalida, paradaVars, intento, fallos>>
       \/ /\ FallaPuerta /\ cap' = RevertirDesde(cur)
          /\ IF intento < MaxIntentos
             THEN /\ intento' = intento + 1 /\ pc' = "tramo12"
                  /\ UNCHANGED <<estado, corriendo, invalida, paradaVars>>
             ELSE AbrirParada("oficio", cur) /\ UNCHANGED intento
          /\ UNCHANGED rev /\ Aprobar
       \/ /\ FallaPuerta
          \* _paquete_o_parada del oficio: la parada se confirma dentro del try, y el
          \* finally revierte el capitulo despues (RevertirTrasParada).
          /\ IF PresupuestoRevierteEnLaParada
             THEN cap' = RevertirDesde(cur) /\ Aprobar
                  /\ AbrirParada("presupuesto", cur)
             ELSE UNCHANGED <<cap, aprobado>>
                  /\ AbrirParadaY("presupuesto", cur, "revertir")
          /\ UNCHANGED <<rev, intento>>
       \/ /\ FallaPuerta /\ cap' = RevertirDesde(cur)
          /\ FallarRun /\ UNCHANGED <<rev, intento, paradaVars>> /\ Aprobar
       \/ /\ pararPendiente /\ cap' = RevertirDesde(cur)
          /\ DetenerRun /\ UNCHANGED <<rev, intento, paradaVars, fallos>> /\ Aprobar
    /\ UNCHANGED <<vivo, planificado, escaleta, p1, p2, escIntento, cur, versiones,
                   lectorVars, pararPendiente, regeneraciones,
                   reinicios>>

\* _avanzar: puerta 5 (nunca bloquea), transicion terminado_* y versiones.publicar en la
\* misma transaccion (RF3-BIB-12). Un cambio del lector fracasado vuelve por aqui, y como
\* el texto no cambio, no publica nada (RF3-CAM-12).
P5 ==
    /\ Corre("p5")
    /\ \E suceso \in {"terminado_limpio", "terminado_con_avisos"} :
          LET e2 == Siguiente(estado, suceso, NINGUNA) IN
          IF e2 = INVALIDA
          THEN FallarPorInvalida /\ UNCHANGED versiones
          ELSE estado' = e2 /\ PublicarCon(rev, aprobado) /\ Acabar /\ UNCHANGED invalida
    /\ UNCHANGED <<paradaVars, vivo, grafoVars, bucleVars, lectorVars, entornoVars>>

\* El finally de generar_capitulo tras la parada de presupuesto del tramo 3: revierte el
\* capitulo a medias en su propia transaccion (pipeline._revertir_a_medias). La parada ya
\* esta confirmada.
RevertirTrasParada ==
    /\ Corre("revertir")
    /\ cap' = RevertirDesde(cur) /\ Aprobar /\ Acabar
    /\ UNCHANGED <<estado, paradaVars, vivo, planificado, escaleta, p1, p2, rev, bucleVars,
                   versiones, lectorVars, entornoVars, invalida>>

(***************************************************************************)
(* El cambio del lector (spec3, 3.8): los capitulos siguen completados, el  *)
(* canon cambiado solo existe en una transaccion que siempre se deshace, y  *)
(* todo se aplica al final en una sola.                                     *)
(***************************************************************************)

\* RF3-CAM-08 y RF3-CAM-09: el revisor corrige el primer capitulo pendiente del alcance y la
\* puerta 4 lo juzga. Hasta MaxIntentos; si los agota, el cambio fracasa sin parada.
LectorRevisar ==
    /\ Corre("lector")
    /\ IF pendLector = {}
       THEN pc' = "lector_aplicar"
            /\ UNCHANGED <<estado, corriendo, invalida, cambio, pendLector, lectorIntento,
                           fallos>>
       ELSE \/ /\ pendLector' = pendLector \ {Min(pendLector)} /\ lectorIntento' = 1
               /\ UNCHANGED <<estado, corriendo, pc, invalida, cambio, fallos>>
            \/ /\ FallaPuerta
               /\ IF lectorIntento < MaxIntentos
                  THEN /\ lectorIntento' = lectorIntento + 1
                       /\ UNCHANGED <<estado, corriendo, pc, invalida, cambio, pendLector>>
                  ELSE /\ cambio' = "fallido" /\ pc' = "p5"
                       /\ UNCHANGED <<estado, corriendo, invalida, pendLector, lectorIntento>>
            \/ /\ FallaPuerta /\ FallarRun /\ cambio' = "fallido"
               /\ UNCHANGED <<pendLector, lectorIntento>>
            \/ /\ pararPendiente /\ DetenerRun /\ cambio' = "interrumpido"
               /\ UNCHANGED <<pendLector, lectorIntento, fallos>>
    /\ UNCHANGED <<paradaVars, vivo, grafoVars, bucleVars, versiones, tipoCambio, alcance,
                   revBase, lenBase, pararPendiente, regeneraciones,
                   reinicios>>

\* Lo que aplica la transaccion final cuando las puertas 1 y 2 siguen valiendo.
AplicarCambio ==
    /\ \E cambiados \in SUBSET alcance :
       \E suceso \in {"terminado_limpio", "terminado_con_avisos"} :
       \E nuevoP1 \in BOOLEAN :
          LET r == [i \in Caps |-> IF i \in cambiados THEN rev[i] + 1 ELSE rev[i]]
              e2 == Siguiente(estado, suceso, NINGUNA)
          IN IF e2 = INVALIDA
             THEN FallarPorInvalida /\ UNCHANGED <<rev, aprobado, p1, p2, versiones, cambio>>
             ELSE /\ rev' = r
                  \* Un capitulo reescrito queda aprobado solo si paso la puerta 4 en la
                  \* simulacion, es decir, si ya no esta pendiente.
                  /\ aprobado' = [i \in Caps |->
                                     IF i \in cambiados THEN aprobado[i] /\ i \notin pendLector
                                     ELSE aprobado[i]]
                  /\ IF CambioRevalidaPuertas \/ tipoCambio = "cambiar_hecho"
                     THEN UNCHANGED <<p1, p2>>
                     ELSE p1' = nuevoP1 /\ p2' = FALSE
                  /\ estado' = e2
                  /\ versiones' =
                        IF Len(versiones) > 0
                           /\ versiones[Len(versiones)].caps = Instantanea(r, aprobado').caps
                        THEN versiones
                        ELSE Append(versiones,
                                    [Instantanea(r, aprobado') EXCEPT !.p1 = p1', !.p2 = p2'])
                  /\ cambio' = "aplicado"
                  /\ Acabar /\ UNCHANGED invalida

\* RF3-CAM-11: canon, textos, puertas 1 y 2 de nuevo, puerta 5, transicion y version, en una
\* transaccion. Un capitulo del alcance puede quedar igual (RF3-CAM-10). Renombrar reescribe
\* filas que leen las huellas de las puertas 1 y 2 (nombre_clave, brief, dedicatoria,
\* escenas). Con CambioRevalidaPuertas, esa misma transaccion las evalua otra vez sobre el
\* canon cambiado; si alguna falla, se deshace entera (CambioImposible) y el cambio fracasa
\* por la puerta 5 con las puertas intactas. Sin eso (el diseno anterior al contraejemplo),
\* la novela quedaba completada con las puertas sin vigencia.
LectorAplicar ==
    /\ Corre("lector_aplicar")
    /\ \/ /\ CambioRevalidaPuertas /\ tipoCambio = "renombrar" /\ FallaPuerta
          /\ cambio' = "fallido" /\ pc' = "p5"
          /\ UNCHANGED <<estado, corriendo, invalida, rev, aprobado, p1, p2, versiones>>
       \/ /\ UNCHANGED fallos
          /\ AplicarCambio
    /\ UNCHANGED <<paradaVars, vivo, planificado, escaleta, cap, bucleVars, tipoCambio,
                   alcance, pendLector, lectorIntento, revBase, lenBase, pararPendiente,
                   regeneraciones, reinicios>>

(***************************************************************************)
(* El worker fuera de avanzar                                               *)
(***************************************************************************)

\* worker._parar, cuando el worker coge la intencion. Si la ejecucion ya no estaba activa,
\* solo deja constancia.
AtenderParar ==
    /\ vivo /\ ~corriendo /\ pararPendiente
    /\ pararPendiente' = FALSE
    /\ IF estado \in Activos
       THEN estado' = Siguiente(estado, "parar", NINGUNA)
       ELSE UNCHANGED estado
    /\ UNCHANGED <<paradaVars, vivo, corriendo, pc, grafoVars, bucleVars, versiones,
                   lectorVars, fallos, regeneraciones, reinicios, invalida>>

\* worker.recuperar, al arrancar tras una caida (RF2-FALLO-06): revierte el capitulo a medias
\* de una ejecucion activa y la deja detenida. Con RecuperarRevierteEnParada, tambien el de
\* una ejecucion en parada, que sigue en parada. No reanuda sola. Un cambio del lector en
\* curso queda interrumpido (RF3-CAM-12).
Recuperar ==
    /\ ~vivo
    /\ vivo' = TRUE
    /\ IF estado \in Activos
       THEN estado' = "detenida" /\ cap' = RevertirDesde(MaxCompletado + 1)
       ELSE IF RecuperarRevierteEnParada /\ estado = "parada"
            THEN cap' = RevertirDesde(MaxCompletado + 1) /\ UNCHANGED estado
            ELSE UNCHANGED <<estado, cap>>
    /\ Aprobar
    /\ cambio' = IF cambio = "reescribiendo" THEN "interrumpido" ELSE cambio
    /\ UNCHANGED <<paradaVars, corriendo, pc, planificado, escaleta, p1, p2, rev, bucleVars,
                   versiones, tipoCambio, alcance, pendLector, lectorIntento, revBase,
                   lenBase, entornoVars, invalida>>

Sistema ==
    \/ Derivar \/ PlanAgentes \/ PlanP1 \/ ChkEsc \/ EscAgente \/ EscP2 \/ ChkGen
    \/ Bucle \/ Tramo12 \/ Tramo3 \/ RevertirTrasParada \/ P5 \/ LectorRevisar \/ LectorAplicar
    \/ AtenderParar \/ Recuperar

(***************************************************************************)
(* El entorno: fallos que nadie elige                                       *)
(***************************************************************************)

\* La API encola 'parar' en cualquier momento.
PedirParar ==
    /\ PuedeFallar /\ Fallar /\ ~pararPendiente
    /\ pararPendiente' = TRUE
    /\ UNCHANGED <<estado, paradaVars, vivo, corriendo, pc, grafoVars, bucleVars, versiones,
                   lectorVars, regeneraciones, reinicios, invalida>>

\* El proceso muere. Cada transaccion es atomica, asi que el grafo queda como estaba.
Caida ==
    /\ PuedeFallar /\ Fallar /\ vivo
    /\ vivo' = FALSE /\ corriendo' = FALSE /\ pc' = "reposo"
    /\ UNCHANGED <<estado, paradaVars, grafoVars, bucleVars, versiones, lectorVars,
                   pararPendiente, regeneraciones, reinicios, invalida>>

(***************************************************************************)
(* El autor: intenciones que el worker atiende cuando no hay nada corriendo *)
(* y la cola no tiene un 'parar' delante                                    *)
(***************************************************************************)
Libre == vivo /\ ~corriendo /\ ~pararPendiente
\* Un reinicio: el autor pone a correr una novela que estaba parada, detenida o en error.
Reiniciar ==
    /\ reinicios < MaxReinicios
    /\ reinicios' = reinicios + 1
Empezar == corriendo' = TRUE /\ pc' = "inicio"
CerrarParada == tipoParada' = NINGUNA /\ capParada' = 0 /\ retcon' = FALSE /\ sabido' = FALSE
\* Toda intencion que reescribe la novela empieza una historia nueva para el cambio.
OlvidarCambio == cambio' = "ninguno" /\ UNCHANGED <<tipoCambio, alcance, pendLector,
                                                   lectorIntento, revBase, lenBase>>

\* worker._arrancar
Arrancar ==
    /\ Libre
    /\ estado \in AdmitenArrancar \cup Activos
    /\ IF estado = "configurada" THEN UNCHANGED reinicios ELSE Reiniciar
    /\ Empezar
    /\ UNCHANGED <<estado, paradaVars, vivo, grafoVars, bucleVars, versiones, lectorVars,
                   pararPendiente, fallos, regeneraciones, invalida>>

\* fallo.relanzar, desde worker._relanzar o desde _resolver_parada con relanzar,
\* aceptar_retcon o dar_por_sabido.
RelanzarDesde(d, suceso) ==
    /\ cap' = RevertirDesde(d)
    /\ Aprobar
    /\ estado' = Siguiente(estado, suceso, tipoParada)
    /\ CerrarParada
    /\ OlvidarCambio
    /\ Empezar

\* worker._relanzar y _resolver_parada con relanzar: _motivo_para_no_relanzar antes.
Relanzar(d) ==
    /\ Libre
    /\ Siguiente(estado, "relanzar", tipoParada) # INVALIDA
    /\ p1 /\ p2
    /\ d \in 1..(MaxCompletado + 1)
    /\ estado \in Completadas => regeneraciones < MaxRegeneraciones
    /\ IF estado \in Completadas
       THEN regeneraciones' = regeneraciones + 1 /\ UNCHANGED reinicios
       ELSE Reiniciar /\ UNCHANGED regeneraciones
    /\ RelanzarDesde(d, "relanzar")
    /\ UNCHANGED <<vivo, planificado, escaleta, p1, p2, rev, bucleVars, versiones,
                   pararPendiente, fallos, invalida>>

\* worker._resolver_parada con aceptar_retcon o dar_por_sabido: relanza desde el capitulo de
\* la parada, y solo si la parada tiene algo que revocar o que dar por sabido.
ResolverContinuidad ==
    /\ Libre
    /\ estado = "parada" /\ tipoParada = "continuidad" /\ capParada # 0
    /\ \E accion \in {"aceptar_retcon", "dar_por_sabido"} :
          /\ IF accion = "aceptar_retcon" THEN retcon ELSE sabido
          /\ RelanzarDesde(capParada, accion)
    /\ Reiniciar
    /\ UNCHANGED <<vivo, planificado, escaleta, p1, p2, rev, bucleVars, versiones,
                   pararPendiente, fallos, regeneraciones, invalida>>

\* fallo.rehacer_estructura y fallo.rehacer_escaleta.
Rehacer ==
    /\ Libre
    /\ estado = "parada" /\ tipoParada \in {"estructura", "escaleta"}
    /\ estado' = Siguiente(estado, "rehacer", tipoParada)
    /\ planificado' = IF tipoParada = "estructura" THEN FALSE ELSE planificado
    /\ p1' = IF tipoParada = "estructura" THEN FALSE ELSE p1
    /\ escaleta' = FALSE /\ p2' = FALSE /\ cap' = Pendiente
    /\ Aprobar
    /\ CerrarParada
    /\ OlvidarCambio
    /\ Empezar
    /\ Reiniciar
    /\ UNCHANGED <<vivo, rev, bucleVars, versiones, pararPendiente, fallos, regeneraciones,
                   invalida>>

\* RF3-CAM-01 a RF3-CAM-06: sobre una novela completada, un cambio de canon con su alcance
\* (que puede salir vacio). Lo que el interprete o la validacion rechazan no cambia nada y
\* no se modela.
CambioDelLector ==
    /\ ConCambioDelLector
    /\ Libre
    /\ estado \in Completadas
    /\ regeneraciones < MaxRegeneraciones
    /\ \E S \in SUBSET Caps, t \in {"renombrar", "cambiar_hecho"} :
          /\ alcance' = S /\ pendLector' = S /\ tipoCambio' = t
    /\ estado' = Siguiente(estado, "cambio_lector", NINGUNA)
    /\ cambio' = "reescribiendo" /\ lectorIntento' = 1
    /\ revBase' = rev /\ lenBase' = Len(versiones)
    /\ regeneraciones' = regeneraciones + 1
    /\ corriendo' = TRUE /\ pc' = "lector"
    /\ UNCHANGED <<paradaVars, vivo, grafoVars, bucleVars, versiones, pararPendiente, fallos,
                   reinicios, invalida>>

\* Lo que el autor hace cuando la novela le espera: no incluye rehacer una ya completada.
AutorResponde ==
    \/ Arrancar
    \/ /\ estado \notin Completadas
       /\ \E d \in 1..(N + 1) : Relanzar(d)
    \/ ResolverContinuidad
    \/ Rehacer

Next ==
    \/ Sistema
    \/ PedirParar \/ Caida
    \/ AutorResponde
    \/ \E d \in 1..(N + 1) : Relanzar(d)
    \/ CambioDelLector

Init ==
    /\ estado = "configurada"
    /\ tipoParada = NINGUNA /\ capParada = 0 /\ retcon = FALSE /\ sabido = FALSE
    /\ vivo = TRUE /\ corriendo = FALSE /\ pc = "reposo"
    /\ planificado = FALSE /\ escaleta = FALSE /\ p1 = FALSE /\ p2 = FALSE
    /\ escIntento = 1 /\ cur = 0 /\ intento = 1
    /\ cap = Pendiente /\ rev = [i \in Caps |-> 0] /\ aprobado = [i \in Caps |-> FALSE]
    /\ versiones = << >>
    /\ cambio = "ninguno" /\ tipoCambio = "renombrar" /\ alcance = {} /\ pendLector = {}
    /\ lectorIntento = 1 /\ revBase = [i \in Caps |-> 0] /\ lenBase = 0
    /\ pararPendiente = FALSE /\ fallos = 0 /\ regeneraciones = 0 /\ reinicios = 0
    /\ invalida = FALSE

\* El sistema no se queda quieto si puede avanzar, y el autor acaba respondiendo a una
\* novela que le espera (parada, detenida, en error o sin arrancar). Ni los fallos, ni la
\* caida, ni las regeneraciones tienen equidad: pueden no ocurrir nunca.
Spec == Init /\ [][Next]_vars /\ WF_vars(Sistema) /\ WF_vars(AutorResponde)

(***************************************************************************)
(* Invariantes de seguridad                                                 *)
(***************************************************************************)
TypeOK ==
    /\ estado \in Activos \cup Reposo \cup {"configurada"}
    /\ tipoParada \in {NINGUNA, "estructura", "escaleta", "continuidad", "oficio", "presupuesto"}
    /\ cap \in [Caps -> {"pendiente", "a_medias", "completado"}]
    /\ cambio \in {"ninguno", "reescribiendo", "aplicado", "fallido", "interrumpido"}
    /\ fallos \in 0..MaxFallos

\* S1. Nunca se publica una version con un capitulo que no paso todas las puertas: tiene los
\* N capitulos, el texto de cada uno paso las puertas 3 y 4 (o, en un cambio del lector, la
\* 4 sobre la correccion), y las puertas 1 y 2 estaban vigentes.
PublicacionConPuertas ==
    \A k \in 1..Len(versiones) :
        /\ versiones[k].total = N /\ versiones[k].ok
        /\ versiones[k].p1 /\ versiones[k].p2

\* S1b. Lo mismo para el estado: una novela completada es una novela entera con sus puertas
\* vigentes. Es la propiedad que rompia el hallazgo 1.
CompletadaConNovela ==
    estado \in Completadas =>
        /\ escaleta /\ p1 /\ p2
        /\ \A i \in Caps : cap[i] = "completado" /\ aprobado[i]

\* S2. La reanudacion no deja capitulos a medias: fuera de una ejecucion y con el worker
\* vivo, ningun capitulo tiene texto y hechos sin cerrar (RF2-PER-07, RF2-FALLO-06).
SinCapituloAMedias ==
    (vivo /\ ~corriendo) => \A i \in Caps : cap[i] # "a_medias"

\* S2b. Solo el capitulo en curso puede estar a medias, y solo entre sus tramos 2 y 3 o
\* hasta que el finally lo revierte.
AMediasSoloElActual ==
    \A i \in Caps : cap[i] = "a_medias" => (i = cur /\ (pc \in {"tramo3", "revertir"} \/ ~vivo))

\* S3. Los reintentos nunca superan el limite.
ReintentosAcotados ==
    /\ intento \in 1..MaxIntentos
    /\ lectorIntento \in 1..MaxIntentos
    /\ escIntento \in 1..2

\* S4. Ningun capitulo se genera sin las puertas 1 y 2 vigentes (RF2-PIPE-00b).
CapituloConPuertas == pc \in {"tramo12", "tramo3"} => p1 /\ p2

\* S5. El orquestador nunca pide una transicion que la maquina no tiene.
SinTransicionInvalida == ~invalida

\* S6. En parada hay exactamente una parada abierta, y fuera de parada ninguna.
ParadaCoherente == (estado = "parada") <=> (tipoParada # NINGUNA)

\* S7. Un cambio del lector solo reescribe los capitulos de su alcance.
SoloElAlcance ==
    cambio \in {"reescribiendo", "aplicado"} =>
        \A i \in Caps \ alcance : rev[i] = revBase[i]

\* S8. Un cambio fracasado o interrumpido no deja nada aplicado (RF3-CAM-12).
CambioFallidoNoAplica ==
    cambio \in {"fallido", "interrumpido"} =>
        rev = revBase /\ Len(versiones) = lenBase

(***************************************************************************)
(* Propiedades de accion                                                    *)
(***************************************************************************)

\* S9. La version anterior se conserva siempre: versiones solo crece.
VersionesInmutables ==
    [][/\ Len(versiones') >= Len(versiones)
       /\ \A k \in 1..Len(versiones) : versiones'[k] = versiones[k]]_vars

\* S10. Reanudar desde el checkpoint no pierde capitulos: la recuperacion conserva todos los
\* completados.
ReanudarNoPierde ==
    [][(~vivo /\ vivo') => {i \in Caps : cap'[i] = "completado"} = Completados]_vars

\* S11. Ni duplica: el texto de un capitulo cambia una vez por cierre, y solo al cerrar su
\* intento en curso o al aplicar un cambio del lector que lo tiene en el alcance.
CierreUnico ==
    [][\A i \in Caps :
          rev'[i] # rev[i] =>
             /\ rev'[i] = rev[i] + 1
             /\ \/ cap[i] = "a_medias"
                \/ pc = "lector_aplicar" /\ i \in alcance]_vars

(***************************************************************************)
(* Liveness                                                                 *)
(***************************************************************************)

\* L1. Toda ejecucion termina: completada, en parada, detenida o en error. Nunca en bucle.
EjecucionTermina == corriendo ~> (vivo /\ ~corriendo /\ estado \in Reposo)

\* L2. Con fallos finitos y un autor que responde, la novela acaba completada y publicada, y
\* se queda asi.
AcabaPublicada == <>[](estado \in Completadas /\ Len(versiones) > 0)

=============================================================================
