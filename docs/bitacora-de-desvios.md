# Bitácora de desvíos

Registro de los momentos en que el agente se fue para otro lado o trabajó con información equivocada: qué pasó, cómo lo detectamos y cómo lo corregimos. Es la fuente de la sección "Qué salió mal" del README.

Formato de cada entrada: fecha, qué pasó, cómo lo detectamos, cómo lo corregimos, qué aprendimos.

## 2026-10-04. Sesión de Claude Code con decisiones desactualizadas

Qué pasó: el 3/10 abrimos una sesión de Claude Code con Superpowers para F0 y F1. La sesión leyó la versión de docs/decisiones-arquitectura.md anterior a la validación con Carlos y empezó a diseñar el modelo viejo (Casillero, VersionTitular, rotación por ciclo). Mientras tanto, el 4/10 Carlos respondió las preguntas de dominio y el modelo cambió: no hay rotaciones, el coordinador no hace guardias y no existe prioridad por descanso.

Cómo lo detectamos: al retomar la sesión, el resumen inicial del agente ("Qué entendí") seguía mencionando entidades que ya habíamos eliminado.

Cómo lo corregimos: no respondimos en esa sesión y la cerramos antes de que escribiera el spec. Guardamos la versión anterior de las decisiones en la branch backup/decisiones-v1, subimos los documentos corregidos mediante el PR #2 y abrimos una sesión nueva. Le pasamos al agente las respuestas a las preguntas técnicas que ya había hecho, para no repetir la ronda.

Qué aprendimos: el contexto de una sesión es una foto del momento en que se abrió. Si cambian las decisiones, se abre una sesión nueva en lugar de corregir la vieja. El resumen "Qué entendí" del inicio es el punto de control para detectar contexto desactualizado.

## 2026-10-05. Defectos del plan corregidos durante la implementación de F0 y F1

Qué pasó: el plan escrito por el agente tenía código que no funcionaba tal cual en cuatro puntos. El formato de log de alembic.ini con `%%` imprimía el texto literal. Una prueba esperaba IntegrityError para un rango de vigencia invertido, pero Postgres rechaza antes el daterange generado con DataError. Pytest no encontraba el paquete `scripts` (se agregó `pythonpath`). La versión de Starlette instalada depreca `httpx` en el TestClient (se silenció el aviso con un filtro). Además, la revisión de la tarea del modelo encontró que las pruebas de restricciones no verificaban qué restricción rechazaba la fila y que una prueba dependía del orden de ejecución.

Cómo lo detectamos: los subagentes implementadores lo reportaron como desvíos al correr las pruebas (TDD), y el revisor de cada tarea los evaluó.

Cómo lo corregimos: con correcciones mínimas aceptadas por el revisor. Las pruebas del modelo se reescribieron para verificar el nombre de la restricción, en una ronda de corrección con nueva revisión.

Qué aprendimos: el código del plan es una hipótesis hasta que corre. Pedirle al implementador que no debilite las pruebas y que reporte cada desvío deja la traza para la revisión.

## 2026-10-07. La revisión de F2 encontró una apropiación de cuentas aprobada en el plan

Qué pasó: la decisión 4 del plan de F2 (aprobada por el equipo) vinculaba por email cualquier Usuario cargado por el seed, sin pedir el código de coordinación, para que Enzo pudiera registrarse. Combinada con D06 (confirmación de email desactivada) y con emails de ejemplo que están en el repositorio, cualquiera con la URL desplegada podía crear en Supabase la cuenta enzo@guardiaviva.test y quedar como coordinador activo, salteando D30. La misma revisión encontró que la vinculación pisaba sin aviso una vinculación hecha en paralelo (regla 8). La implementación seguía el plan al pie de la letra: el error estaba en el plan, no en el código.

Cómo lo detectamos: la revisión de código de toda la branch, hecha por un subagente con contexto nuevo después de las seis tareas, cruzó la decisión 4 con D06 y con los emails del seed.

Cómo lo corregimos: el equipo eligió exigir el código para vincular un coordinador cargado (422 CODIGO_REQUERIDO) y aceptar el riesgo para los médicos cargados; quedó en D28 y en la decisión 4 del plan. La vinculación pasó a un UPDATE condicionado a auth_id vacío que responde 409 si otra cuenta ganó. Cada corrección empezó con una prueba que fallaba.

Qué aprendimos: aprobar decisiones una por una no alcanza; hay que mirarlas combinadas con las anteriores (acá, la 4 con D06). La revisión final con contexto nuevo es la que ve esos cruces.

## 2026-10-07. Menores de la revisión de F2 que quedan pendientes

Qué pasó: la revisión de código de F2 marcó siete puntos menores. Antes del pull request se corrigieron tres, cada uno en su commit: el umbral de la alerta limitado a 48H, 24H e INICIO; TOKEN_SIN_EMAIL con 403; y la aclaración sobre turno.creado_en en backend/CLAUDE.md. Los otros cuatro quedan pendientes:

1. Si el endpoint de claves públicas de Supabase (JWKS) responde algo que no es JSON (por ejemplo, la página de error de un proxy), PyJWT lanza un ValueError que no captura, y el backend responde 500 sin el formato de error. Si el JWKS llega sin claves, responde 401 TOKEN_INVALIDO aunque el problema sea de Supabase. Corrección propuesta: capturar ValueError alrededor de la búsqueda de la clave y responder 503 AUTH_NO_DISPONIBLE.
2. pyproject.toml pide `pyjwt[crypto]>=2.9`, pero la espera mínima antes de volver a pedir claves por un `kid` desconocido existe solo en versiones recientes. Subir el mínimo a la versión probada (2.15).
3. Al vincular un médico cargado, un código de coordinación correcto se ignora (decisión 4 del plan) y la respuesta no lo avisa. La interfaz de F6 tiene que explicarlo o la respuesta tiene que sumar un campo.
4. POST /api/registro no limita los intentos, y la respuesta 422 CODIGO_INVALIDO deja probar códigos sin límite. D30 ya reconoce que el código es un control simple; como mínimo, recomendar en .env.example un código largo y difícil de adivinar.

Cómo lo detectamos: revisión de código de toda la branch feature/f2-cimientos.

Cómo lo corregimos: todavía no; se anotan para F5 (seguridad y staff) o F6 (interfaz), según corresponda.

Qué aprendimos: separar en la revisión lo que bloquea el merge de lo que se puede anotar deja el pull request chico sin perder los hallazgos.

## 2026-10-07. La revisión de F5 encontró carreras en la baja y un callejón sin salida en la plantilla

Qué pasó: la revisión de toda la branch feature/f5-staff-backend reprodujo tres problemas importantes contra la base de pruebas. Primero, si un coordinador designaba un titular nuevo mientras otro daba de baja al titular anterior, la baja dejaba sin titular al recién designado: leía los horarios del médico antes de bloquearlos y no los volvía a mirar. Segundo, un médico con una versión que todavía no empezó no podía darse de baja ni pasar a coordinador, y esa versión no se podía corregir por ninguna ruta: el plan (decisiones 4 y 7) no previó el caso. Tercero, un PATCH con estado y rol bloqueaba al usuario antes que a los coordinadores, contra el orden de bloqueos del propio plan, y podía terminar en un deadlock que llegaba como 500.

Cómo lo detectamos: revisión de código de toda la branch por un subagente con contexto nuevo, con foco pedido en el orden de los bloqueos. El revisor escribió sondas de concurrencia propias fuera del repositorio.

Cómo lo corregimos: cada corrección empezó con una prueba que fallaba (dos de ellas commit_real, con dos transacciones reales). La baja vuelve a mirar cada horario después de bloquearlo. El PATCH activa dentro de cambiar_rol, sobre las filas ya bloqueadas en orden. Para el segundo, el equipo eligió que una versión que todavía no rige se modifique en el lugar (ajuste en D10). Además, por pedido del equipo, pasar a coordinador exige un usuario activo y un deadlock o choque de versiones responde 409.

Qué aprendimos: las pruebas de concurrencia del plan cubrían las carreras que el plan había imaginado; las que encontró la revisión mezclaban dos operaciones distintas (designar y dar de baja). Conviene pensar las carreras por pares de operaciones, no por operación.

## 2026-10-07. Menores de la revisión de F5 que quedan pendientes

Qué pasó: la revisión de F5 marcó cinco puntos menores. Se corrigieron dos (cambio a coordinador solo con usuario activo; deadlock y choque de versiones como 409). Los otros tres quedan pendientes:

1. La fábrica de pruebas `bloqueado_hasta_commit` verifica que la segunda transacción espera con un `join(timeout=0.5)`: prueba que el hilo no terminó, no que esté esperando un bloqueo. En una máquina lenta la prueba podría pasar sin probar la espera (falso positivo, no falla al azar). Corrección propuesta: consultar `pg_blocking_pids` o `pg_stat_activity` hasta ver la espera por bloqueo.
2. El docstring de `test_dos_coordinadores_no_pueden_quitarse_el_rol_a_la_vez` atribuye la garantía a que Postgres vuelve a evaluar el WHERE (EvalPlanQual), pero el filtro en Python con `populate_existing` daría el mismo resultado. Corrección propuesta: ajustar el texto a lo que la prueba realmente demuestra.
3. Los permisos (`requiere_coordinador`) se leen antes de tomar los bloqueos: un coordinador al que otro le quita el rol puede terminar una acción que ya había empezado. La garantía de "al menos un coordinador activo" no se ve afectada. Es una ventana de milisegundos, común a toda la API.

Cómo lo detectamos: revisión de código de toda la branch feature/f5-staff-backend.

Cómo lo corregimos: todavía no; quedan anotados para después del Demo Day o para cuando se toque ese código.

Qué aprendimos: igual que en F2, separar lo que bloquea el merge de lo que se puede anotar mantiene el pull request chico sin perder los hallazgos.

## 2026-10-08. Decisiones propias del plan de F4 historia y alertas, backend

Qué pasó: D19, D20, D22, D24 y D27 dejaban abiertos varios puntos de la consolidación, las alertas, las notificaciones y el reloj de demo. El agente los cerró en la sección "Decisiones de este plan" de `docs/superpowers/plans/2026-10-08-f4-historia-alertas-backend.md`, cada uno con su costo si está mal:

1. **Marca de consolidación** (tabla `consolidacion_estado`, una fila): los turnos calculados con fecha anterior a la marca ya se materializaron y consolidaron. Sin marca, cada consulta recalcularía todos los turnos desde la primera vigencia. La primera vez se parte de la primera `vigente_desde`. Es seguro porque ningún cambio de plantilla empieza antes de hoy (backend/CLAUDE.md, punto 12). Costo: si alguien carga una versión con vigencia pasada por SQL, esos turnos no se consolidan. *Ajustada en la revisión (ver la entrada siguiente):* el supuesto no alcanzaba para los cambios que empiezan hoy.
2. **La fila de la marca se bloquea** (`FOR UPDATE`) en cada consolidación: dos consultas simultáneas se esperan en lugar de duplicar trabajo. Costo: `GET /turnos` se serializa durante la consolidación (milisegundos con 12 usuarios).
3. **Consolidar con una vacante abierta la cierra como `SIN_COBERTURA`**, completa `sin_cobertura_en` y escribe `TURNO_SIN_COBERTURA` con actor sistema (`actor_id` NULL) y `datos = {"vacante_id", "al_consolidar": true}`. D19 dice que se consolida sin realizador; dejar la vacante abierta para siempre mostraría como abiertas vacantes de turnos pasados. Costo: un evento de sistema que D22 no lista para este caso.
4. **`POST /turnos/{id}/sin-cobertura` exige una vacante abierta y que el turno haya empezado** (D19: "si al llegar el inicio la vacante sigue abierta"). Antes del inicio responde 422 `TURNO_NO_EMPEZO`. Un turno BAJA sin vacante no se marca: si nadie lo cubre, la consolidación lo deja sin realizador y cuenta igual en el indicador (D24). No envía notificaciones: no hay a quién avisar algo nuevo.
5. **Alertas solo para turnos con vacante abierta** (D19 las define sobre la vacante). Los turnos BAJA sin vacante ya se ven en rojo (D24) y no generan alertas.
6. **Si vencieron varios umbrales a la vez** (servidor caído o reloj de demo adelantado), se registran todos los eventos `ALERTA_SIN_COBERTURA` (para que no se disparen después) y se manda **una sola** notificación, la del umbral más reciente. Costo: el evento de 48 h existe aunque nadie recibió ese aviso.
7. **Las alertas se evalúan en cada `GET /notificaciones`** (lo consulta cada usuario cada 10 a 15 s, D05) además de `GET /turnos`. Así llegan a tiempo sin proceso programado. El índice único `ux_evento_alerta_por_umbral` y el `INSERT ... ON CONFLICT DO NOTHING` garantizan una sola alerta por turno y umbral aunque dos pedidos lleguen juntos. `GET /notificaciones` no consolida (para no bloquear la marca en cada consulta periódica).
8. **Destinatarios "con acceso"**: ACTIVO, o BAJA hasta su `fecha_baja` inclusive (la misma regla que `usuario_actual`, D24). `destinatarios(...)` es la función que Mariano usará para `VACANTE_URGENTE`.
9. **Reloj de demo en memoria** (desfase en una variable del módulo `app/reloj.py`): un solo proceso de uvicorn en la demo. `POST /demo/reloj` con `{"ahora": instante}` solo avanza (422 `RELOJ_HACIA_ATRAS`), y `{"ahora": null}` vuelve a la hora real (pensado para usar después del seed). Solo coordinadores. Fuera de modo demo responde 404 y no aparece en `/docs`. Costo: reiniciar el servidor vuelve a la hora real; con varios procesos cada uno tendría su desfase. *Reemplazada en la revisión (ver la entrada siguiente):* el desfase se guarda en la base.
10. **El indicador cuenta turnos consolidados sin realizador** (sin cobertura, vacante abierta al terminar y horarios BAJA sin cubrir), agrupados por el mes de su fecha de inicio (D13). Rango `desde`/`hasta` en `AAAA-MM`, hasta 24 meses, con meses en cero incluidos. Una rectificación que agregue realizador lo saca del indicador.
11. **Tipos de notificación**: `TipoNotificacion` en `app/dominio/notificaciones.py` con `VACANTE_URGENTE` (la usa Mariano) y `ALERTA_SIN_COBERTURA`. Quien necesite otro tipo lo agrega al enum; la columna sigue siendo texto (sin migración).
12. **Fuera de este plan:** rectificación (`POST /turnos/{id}/rectificacion`), `GET /turnos/{id}`, estado de los turnos dentro de `GET /turnos` y frontend. `GET /turnos` sigue devolviendo exactamente el mismo JSON.

Cómo lo detectamos: el plan las lista para aprobarlas antes de ejecutar.

Cómo lo corregimos: el equipo aprobó el plan completo. La revisión de la branch cambió la 9 y acotó la 1 (entrada siguiente).

Qué aprendimos: escribir el costo de cada decisión ayudó a la revisión: los dos problemas que encontró estaban en las decisiones cuyo costo el plan había subestimado.

## 2026-10-08. La revisión de F4 encontró historia incorrecta en la consolidación y en el reloj de demo

Qué pasó: la consolidación era idempotente y segura frente a concurrencia, pero podía guardar historia incorrecta por tres caminos, y el orden de bloqueos documentado invitaba a un deadlock.

1. Un cambio de plantilla que empieza hoy (cambiar el titular, cerrar o crear un horario) alcanzaba al turno de hoy ya empezado y todavía sin fila. Según cuándo corriera la consolidación, lo guardaba con el titular nuevo, lo perdía o inventaba un turno que no ocurrió. El supuesto de la decisión 1 ("ningún cambio de plantilla empieza antes de hoy") no alcanzaba.
2. `{"ahora": null}` en el reloj de demo volvía a la hora real después de haber consolidado con el reloj adelantado. Quedaban turnos consolidados con fin en el futuro, vacantes cerradas en el futuro y la marca adelantada, y los turnos de un horario creado después con fecha anterior a la marca no se consolidaban nunca. La decisión 9 decía "solo avanza", pero `null` lo esquivaba, y el seed no reiniciaba el desfase en memoria.
3. Cada turno que inserta la consolidación toma FOR KEY SHARE sobre su horario, su versión y sus usuarios. El orden documentado (usuario, horario, marca) invitaba a consolidar después de bloquear un horario, y eso cierra un ciclo con `GET /turnos`.
4. Un turno guardado (con foto o asignado) de un médico dado de baja antes de la fecha del turno se consolidaba con él como realizador. La revisión lo marcó menor; lo subimos a importante porque es historia incorrecta.

Cómo lo detectamos: revisión de toda la branch feature/f4-historia-alertas por un subagente con contexto nuevo, con foco pedido en que la consolidación sea idempotente y no guarde historia incorrecta. El revisor confirmó los puntos 1 y 2 con pruebas temporales.

Cómo lo corregimos:

1. El cambio de plantilla que empieza hoy responde 422 `TURNO_DE_HOY_EMPEZADO` si el turno de hoy de ese horario ya empezó y no está guardado. Se verifica antes y después del cambio, con la versión vieja y con la nueva. Se descartó guardar la foto del turno en curso porque contradice la regla 1 de CLAUDE.md (D11). Costo: en ese caso el coordinador usa "desde mañana". Prueba: `tests/test_plantilla_turno_de_hoy.py`.
2. El desfase del reloj de demo se guarda en `consolidacion_estado.desfase_demo` (migración 0004). El seed vacía esa fila, así que reiniciar la demo vuelve a la hora real y además funciona con varios procesos. `null` responde 409 `REINICIAR_DEMO` si ya se registró historia después de la hora real. Costo: una consulta más por pedido en modo demo. Pruebas en `tests/test_api_demo.py` y `tests/test_reloj.py`.
3. Convención 19 de `backend/CLAUDE.md`: la consolidación se llama al principio de la transacción, antes de bloquear usuarios u horarios. Solo documentación: hoy no hay ciclo en el código.
4. La consolidación deja sin realizador un turno guardado cuyo realizador presunto se dio de baja antes de la fecha del turno. Prueba: `test_titular_o_asignado_dado_de_baja_antes_del_turno_no_es_realizador`.

Queda pendiente un menor: cuando la consolidación cierra una vacante abierta, usa la hora de la consolidación (no la del fin del turno) en `sin_cobertura_en`, `cerrada_en` y `ocurrido_en`. Si nadie abre la app por días, esa hora queda lejos del fin del turno.

Qué aprendimos: un supuesto sobre la plantilla ("nada empieza antes de hoy") no alcanza cuando "hoy" ya tiene turnos en curso: el límite real es el instante, no la fecha. Y una herramienta de demo que mueve el tiempo tiene que guardar su estado junto con la historia que produce, para que el reinicio vuelva todo atrás a la vez.

## 2026-10-08. Tarea 11 de F5: el plan reabría las coberturas antes de bloquear los horarios

Qué pasó: el paso 5 de la tarea 11 del plan de F5 decía llamar a `_reabrir_coberturas` antes de `dejar_sin_titular`. Eso bloquea turnos antes que horarios, al revés del orden de la convención 19 de `backend/CLAUDE.md` (usuario, horario, consolidación, turno, vacante), que se escribió en F4, después del plan. Además, la firma real de `generar_vacante` recibe el id "horarioId:fecha" y la zona, no el turno.

Cómo lo detectamos: al ejecutar el paso 1 (confirmar la función de Mariano) y contrastarla con `backend/CLAUDE.md` antes de escribir el código.

Cómo lo corregimos: la baja y el cambio a coordinador reabren al final, después de dejar los horarios sin titular y de cambiar estado o rol. `coberturas_desde` bloquea los turnos por (horario, fecha), como `bloquear_turnos` (convención 20). La firma real quedó anotada en el paso 1 del plan.

Qué aprendimos: una tarea marcada como dependiente envejece mientras espera; hay que contrastarla con las convenciones que se sumaron después, no solo con la función de la que depende.

## 2026-10-08. La decisión de los postulantes en BAJA se numeró D34 porque D33 ya existía

Qué pasó: el prompt de feature/postulantes pedía agregar la decisión "turno en BAJA con postulantes en ámbar" como D33, pero D33 ya existía en `docs/decisiones-arquitectura.md` ("Asignación y candidatos", de F3).

Cómo lo detectamos: el agente buscó D33 en la documentación y el código antes de escribir; aparecía en `docs/decisiones-arquitectura.md`, en la convención 24 de `backend/CLAUDE.md` y en el commit 80a7c58.

Cómo lo corregimos: la decisión nueva se numeró D34 y así se cita en el código, en `backend/CLAUDE.md` y en el pull request #26. El agente lo avisó al entregar y el equipo lo aprobó ("Bien D34").

Qué aprendimos: antes de pedir una decisión nueva conviene mirar el último número usado; reusar un código haría que dos decisiones distintas se citen igual en specs, planes y commits.
