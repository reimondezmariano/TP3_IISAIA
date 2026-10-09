# Guardia Viva: decisiones de arquitectura

Registro de las decisiones tomadas durante el brainstorming de arquitectura (2 y 3 de octubre de 2026) y de los ajustes tras validar el modelo con un médico del servicio (4 de octubre de 2026). Cada decisión indica las alternativas consideradas y el motivo de la elección. Este documento es la fuente de la sección "Qué decidí yo" del README.

Equipo: Carlos Lugones, Mariano Reimondez, Florencia Lucca.

## Contexto

Un servicio hospitalario de 10 a 12 médicos gestiona hoy sus guardias con un grupo de WhatsApp y una planilla Excel que actualiza el coordinador. Guardia Viva reemplaza ese mecanismo con una aplicación web instalable en el celular, un backend con API y persistencia.

Cómo funciona el servicio (validado con Carlos, médico de guardia):
1. Cada médico, al ingresar, pacta sus días y horarios. Como regla general se repiten todas las semanas, y hay médicos que hacen un horario semana por medio. Cada horario tiene un solo médico. La duración varía según el médico: 6, 7, 8, 12 o 24 horas.
2. Los médicos no trabajan todos los días: muchos hacen uno o dos días por semana, y cada uno decide su carga. No hay prioridad por descanso ni descanso mínimo obligatorio.
3. El coordinador no hace guardias ni cubre vacantes.
4. Cuando nadie cubre una ausencia, no se hace nada: los demás médicos trabajan el doble.
5. Las ausencias se avisan con anticipación muy variable: meses (vacaciones, congresos) o minutos (una urgencia familiar).
6. En los feriados cada médico cumple su horario habitual.
7. Cada médico y cada coordinador ingresa con usuario y contraseña. Cuando un médico deja el servicio, su lugar queda sin titular hasta que se designa a otra persona; mientras tanto otros pueden cubrirlo, pero debe quedar claro que es por la baja del titular.

Criterio rector: el modelo más simple que preserve correctamente las reglas del dominio, la concurrencia, la historia y la trazabilidad. Plazo: Demo Day el 14/10/2026, con la aplicación lista el 11/10 para probar.

## Herramientas y proceso

D01. Brainstorming de dominio y arquitectura en una conversación con Claude (sin código). Implementación con Claude Code y el plugin Superpowers dentro del repositorio.
Motivo: el README pide spec, plan, commits, branches y pull requests como evidencia del proceso; Superpowers los produce como subproducto (docs/superpowers/specs, docs/superpowers/plans, una branch por funcionalidad, un commit por tarea).

## Plataforma

D02. Persistencia en Supabase (Postgres gestionado). Se descartó Google Drive.
Alternativas: Google Sheets (sin transacciones ni unicidad, concurrencia frágil), SQLite (simple, pero difícil de desplegar con datos persistentes en hostings gratuitos).
Motivo: transacciones, restricciones únicas, índices parciales y restricciones de exclusión resuelven la concurrencia en la base. Accesible desde internet para una demo con varios usuarios.

D03. Backend en Python con FastAPI.
Alternativas: Node con Express; Supabase consumido directamente desde el frontend (descartado: no hay servidor propio ni endpoints, y el README pide ambos).
Motivo: genera automáticamente la documentación OpenAPI navegable en /docs, que es el contrato entre interfaz y servidor que pide el README. Python es el lenguaje común de la maestría.

D04. Acceso a datos con SQLAlchemy y migraciones con Alembic.
Motivo: estándar con FastAPI; cada cambio de esquema queda como migración numerada en el repositorio.

D05. Interfaz web responsive instalable en el celular (PWA), hecha con React y Vite en la carpeta frontend/. El prototipo HTML del equipo se usa como referencia visual. En producción el backend sirve la compilación como estáticos, para tener un solo despliegue.
Alternativa descartada: adaptar el prototipo en HTML y JavaScript sin framework. Era menos trabajo, pero un framework ordena mejor las varias pantallas (calendario, candidatos, staff, login) y el estado que se actualiza con las notificaciones. Notificaciones dentro de la app, consultadas cada 10 a 15 segundos. Las vacantes urgentes (menos de 24 h de anticipación) se muestran además como aviso emergente (pop-up) en la aplicación, para todos los médicos que la tengan abierta. Push nativo, Web Push y mail quedan como trabajo futuro.
Motivo: el README evalúa la aplicación de punta a punta, no el canal de notificaciones. Web Push en iPhone exige instalar la app y es frágil en vivo.

D06. Autenticación con Supabase Auth, con email y contraseña. Las contraseñas las gestiona Supabase Auth; nunca se guardan en las tablas propias. Confirmación de email desactivada, para no depender del envío de mails. El backend verifica el token y vincula la cuenta con el Usuario por el identificador de Supabase Auth. Los permisos se validan en el backend aunque la interfaz oculte las acciones. "Olvidé mi contraseña" queda como trabajo futuro.
Cambio tras validar con Carlos: el diseño anterior usaba login con Google. Carlos indicó usuario y contraseña, que además funciona con cualquier email.

D30. Registro con código de coordinación. Cada persona crea su cuenta (nombre, email, contraseña) y elige su propia contraseña. Si ingresa el código de coordinación del servicio (por ejemplo, SMG), la cuenta queda como coordinador activo; sin código queda como médico pendiente, sin acceso, hasta que un coordinador lo activa desde la pantalla de staff. El código se valida en el backend y se configura como variable de entorno; nunca está en el frontend ni en el repositorio.
Motivo: es la opción más simple de implementar (sin contraseñas temporales ni invitaciones por mail) y resuelve el alta del primer coordinador. Limitación reconocida: un código compartido es un control simple; en producción se reemplazaría por invitaciones.

D07. Seguridad por filas (RLS) activada en todas las tablas, sin políticas. El frontend usa Supabase solo para el login; el backend se conecta a Postgres con credenciales propias.
Motivo: Supabase publica las tablas en una API accesible con la clave pública; sin RLS cualquiera podría saltear las reglas del backend.

## Modelo de dominio

D08. Modelo C5: turno materializado perezosamente, entidades operativas y bitácora mínima.
Alternativas analizadas:

| Modelo | Descripción | Por qué no |
|---|---|---|
| C1 | Plantilla + excepciones + snapshot GuardiaRealizada | Redundancia entre turno y snapshot; las rectificaciones sobrescriben; las decisiones del coordinador no quedan registradas |
| C1.5 | Entidades ricas con fechas y responsables, sin bitácora | Pierde valores anteriores en rectificaciones y reasignaciones, y el contexto de cada decisión |
| C4 | C1.5 + bitácora de eventos completa | Duplica las entidades y abre la puerta a inconsistencias entre estado y bitácora |
| C5 (elegido) | C4 depurado | |

Diferencias de C5:
1. Turno y guardia realizada son la misma fila en distintos momentos.
2. La postulación se hace al turno, no a la vacante.
3. El semáforo se calcula, no se guarda.
4. No existe una tabla Asignacion: el turno guarda el asignado actual y la bitácora conserva los anteriores.
5. La bitácora registra solo acciones y solo lo que ninguna entidad conserva.

Entidades: Usuario, HorarioPactado, VersionHorario, Turno, Vacante, Postulacion, EventoTurno, Notificacion.

D09. Identidad del turno = horario pactado + fecha de inicio. En la API, identificador compuesto "horarioId:fecha" (por ejemplo, 7:2026-10-10). Existe aunque el turno nunca se haya guardado y no cambia aunque cambie la plantilla.

D10. Plantilla como horarios pactados versionados: HorarioPactado (identidad estable) y VersionHorario (médico titular, opcional para los horarios sin titular de D24; día de la semana, hora de inicio, duración, frecuencia en semanas, fecha ancla, vigenteDesde, vigenteHasta). Una renegociación o un cambio de titular cierra la versión vigente y abre otra. Las vigencias de un horario no se superponen (restricción de exclusión de Postgres). Que horarios de distintos médicos se superpongan es normal: hay varios médicos de guardia a la vez.
Alternativa descartada: una sola tabla con vigencias, donde cada versión tiene otro identificador y deja colgadas las excepciones futuras.
Ajuste del 5/10/2026 (spec de F0 y F1): el texto anterior decía que el HorarioPactado pertenecía a un médico; el médico va en la versión, como ya indicaban D24 y CLAUDE.md.
Ajuste del 7/10/2026 (revisión de F5): una versión que todavía no rige (empieza después de hoy) se modifica en el lugar en lugar de abrir otra: nunca rigió, así que no tiene historia que conservar. Una versión que ya rige nunca se modifica. Sin este ajuste, un médico con un horario cargado a futuro no podía darse de baja ni pasar a coordinador hasta que ese horario empezara.

D11. Materialización perezosa: el turno se calcula desde la plantilla mientras no le pasa nada. Se guarda como fila cuando se genera una vacante o cuando se consolida. Al crearse copia inicio, fin, versión y médico titular, que no se recalculan. Restricción única sobre (horario, fecha).
Alternativa descartada: materializar todos los turnos de las próximas N semanas (obliga a regenerar y reconciliar ante cada cambio de plantilla).

D12. Un cambio de plantilla nunca rompe lo ya asignado. Las excepciones existentes conservan su snapshot y el coordinador recibe la lista de turnos afectados.

D13. Horario expresado como hora de inicio + duración. El turno pertenece a la fecha en que empieza. Zona horaria America/Argentina/Buenos_Aires; instantes guardados con zona horaria. La semana empieza el lunes.

D14. Frecuencia en lugar de rotación: cada horario pactado tiene un solo médico y una frecuencia en semanas (1 = todas las semanas, que es el caso general; 2 = semana por medio; 3 = cada tres semanas) con una fecha ancla, que es el lunes de una semana en que el horario se cumple. El horario se cumple en la semana S si la cantidad de semanas entre la fecha ancla y S es múltiplo de la frecuencia.
Cambio tras validar con Carlos: el diseño anterior soportaba varios titulares rotativos por horario. Carlos confirmó que cada horario es de una sola persona, pero que hay médicos que toman un horario semana por medio. Se eliminó la entidad VersionTitular y se conservó solo la frecuencia. Si alguna vez dos médicos se alternan un mismo horario, se representa con dos horarios de frecuencia 2 desfasados una semana.

## Reglas operativas

D15. Vacantes. Las genera el médico titular o asignado del turno, o un coordinador. Cada vacante corresponde a un solo turno; una ausencia de varios días son varias vacantes independientes (la interfaz permite marcar varias fechas en una acción, útil para vacaciones y congresos). El titular puede retirar la vacante mientras no haya asignación. Como máximo una vacante abierta por turno. Una vacante generada con menos de 24 h de anticipación se marca como urgente y se destaca para todos.

D16. Postulaciones al turno. La oferta de un médico vale para el turno mientras no ocurra y no la retire. Si el asignado cancela y se abre otra vacante, los candidatos anteriores siguen activos: son la reserva para cancelaciones de último momento y reciben una notificación para retirarse si ya no pueden. No se postula el titular a su propio turno ni un médico con una guardia superpuesta. La elegibilidad se calcula al consultar: si un impedimento desaparece, el candidato vuelve a ser elegible.

D17. Candidatos ordenados por equidad: primero quien cubrió menos vacantes en el mes calendario del turno. Cuenta como cobertura cada turno de ese mes en que el médico quedó asignado sin ser el titular. Desempate: hora de postulación según el servidor. Dato informativo que no altera el orden: horas de guardia del médico en esa semana. El orden es un apoyo: el coordinador puede elegir a cualquier candidato.
Cambio tras validar con Carlos: el diseño anterior ordenaba por horas de descanso previo, con advertencia por menos de 12 h. Carlos explicó que en el servicio no existe prioridad por descanso: los médicos hacen uno o dos días por semana y cada uno decide su carga. Propuso en cambio repartir la carga extra de forma equitativa. Se eliminaron el ranking por descanso y la advertencia.

D18. Asignación con un solo endpoint. "Esta persona cubre este turno" cubre tres casos que el backend distingue: elección de un candidato, asignación directa de alguien que no se postuló, y reasignación. El coordinador puede elegir a cualquier candidato.

D19. Turno sin cobertura. Alertas escalonadas a los coordinadores a las 48 h, a las 24 h y al inicio, una sola vez por turno y umbral. Si al llegar el inicio la vacante sigue abierta, el coordinador asigna a alguien o marca el turno como "sin cobertura". Se consolida sin realizador.
Indicador para el coordinador: horas sin cobertura por mes. Hoy, cuando nadie cubre, los demás médicos trabajan el doble y el problema no queda registrado; el indicador lo hace visible.

D20. Consolidación perezosa e idempotente. Antes de responder consultas de calendario, el backend consolida los turnos terminados; el coordinador también puede forzarla. Al terminar un turno cubierto, se presume realizado por el asignado vigente (o el titular). Tolera caídas del servidor porque no depende de un proceso programado.

D21. Rectificación (endpoint propio, solo coordinadores). El coordinador corrige quién realizó una guardia consolidada, con motivo obligatorio. Queda un evento con el valor anterior.

D22. Bitácora (EventoTurno) solo de agregar, escrita en la misma transacción que el cambio. Distingue actor humano y sistema. Eventos: VACANTE_GENERADA, VACANTE_RETIRADA, POSTULACION_CREADA, POSTULACION_RETIRADA, CANDIDATO_ELEGIDO (con la posición en la lista y la cantidad de candidatos), ASIGNACION_DIRECTA, REASIGNACION, TURNO_SIN_COBERTURA, REALIZADOR_RECTIFICADO, ALERTA_SIN_COBERTURA. Excluidos: consolidación normal (ya está en consolidadoEn), consultas, logins, lecturas de notificaciones y cambios de plantilla (las versiones ya son su historia).

D23. Roles excluyentes: cada usuario es MEDICO o COORDINADOR, con estado PENDIENTE, ACTIVO o BAJA. El coordinador no tiene horarios pactados, no se postula y no cubre vacantes. El rol puede cambiar de persona y puede haber varios coordinadores; siempre debe quedar al menos un coordinador activo. Un médico que pasa a coordinador deja antes sus horarios sin titular.
Cambio tras validar con Carlos: el diseño anterior suponía que el coordinador también era médico de guardia.
Ajuste del 7/10/2026 (plan de F5): el cambio de médico a coordinador deja sus horarios sin titular desde el día siguiente en la misma acción. "Al menos un coordinador activo" se garantiza bloqueando en la base las filas de los coordinadores activos.

D24. Baja definitiva de un médico: fecha de baja (activo hasta ese día inclusive); desde esa fecha no puede ingresar. Sus horarios pactados quedan sin titular desde la fecha de baja (nueva versión del horario sin médico). Cada guardia de un horario sin titular se calcula en rojo con la etiqueta BAJA, distinta de una vacante común. Mientras tanto, cada guardia se puede cubrir con el circuito habitual de postulación y asignación, y se muestra como cubierta por baja del titular. Cuando el coordinador designa un nuevo titular, se crea una nueva versión del horario desde esa fecha. El coordinador también puede cerrar el horario. Las coberturas que el médico había aceptado para turnos posteriores se reabren como vacantes comunes. Las horas sin cubrir cuentan en el indicador de D19. Nunca se borra un usuario.
Cambio tras validar con Carlos: el diseño anterior obligaba a transferir o cerrar cada horario en el momento de la baja. Carlos indicó que el lugar debe quedar visible como baja hasta designar a otra persona.
Ajuste del 7/10/2026 (plan de F5): la fecha de baja es el último día activo; los horarios quedan sin titular desde el día siguiente. El estado pasa a BAJA al registrarla y la cuenta entra hasta esa fecha inclusive. No se registran bajas con fecha pasada. Solo se da de baja a médicos; un coordinador pasa antes a médico. El coordinador también puede cerrar un horario (POST /horarios/{id}/cierre).

D25. Motivo de la ausencia: se informa al generar la vacante y es visible solo para los coordinadores; el resto del servicio ve solo que el turno está vacante.
Motivo: puede incluir información personal o de salud que no corresponde mostrar a todo el servicio.

## Alcance para el Demo Day

D26. Pantalla de staff completa para el coordinador: lista de usuarios con rol, estado y horarios pactados; activar médicos pendientes, cargar y modificar horarios (cada cambio es una nueva versión), cambiar el rol, dar de baja y designar nuevo titular en los horarios marcados BAJA. Los datos de ejemplo se cargan por script.

D27. Reloj de demo: en modo demo (variable de entorno) un endpoint adelanta la hora del sistema para mostrar consolidación y alertas. Las pruebas usan el mismo mecanismo. No existe fuera del modo demo.

D28. Demo: un usuario coordinador "Enzo" con un email creado por el equipo; los tres integrantes actúan como médicos. Si Enzo quiere operar en vivo, se agrega su email. Plan de respaldo: todo desde una computadora.
Cambio en F2 (7/10/2026): los usuarios cargados por el seed se vinculan a su cuenta de Supabase por email al registrarse. Como la confirmación de email está desactivada (D06), cualquiera puede crear la cuenta de un email cargado; por eso vincular un coordinador cargado exige el código de coordinación (D30). Los médicos cargados se vinculan activos sin código: riesgo aceptado para la demo, porque sus emails no se publican fuera del repositorio y un médico no tiene permisos de coordinación.

D29. Fuera de alcance: coberturas parciales, intercambios directos entre médicos, push nativo, mail.

D31. Al generar una vacante, si el turno tenía un asignado, el asignado se borra en la misma transacción y queda registrado en la bitácora con VACANTE_GENERADA (D08 punto 4). Como defensa, la consolidación da prioridad a la vacante abierta sobre el asignado y el titular: con una vacante abierta al terminar el turno no hay realizador presunto (D19, D20).
Alternativa descartada: conservar el asignado mientras la vacante está abierta y resolver quién manda en cada consulta. Cada lugar que lee el turno (consolidación, candidatos, semáforo, equidad) tendría que acordarse de ignorar al asignado cuando hay una vacante, y un olvido atribuiría la guardia, o una cobertura en el orden de D17, a quien acaba de cancelar.
Motivo: D08 punto 4 dice que no existe una tabla Asignacion: el turno guarda solo el asignado actual y la bitácora conserva los anteriores. Borrarlo junto con la vacante, en la misma transacción que el evento (D22), mantiene un único estado posible: turno con vacante abierta es turno sin asignado. La prioridad en la consolidación queda como defensa ante un dato inconsistente.

D32. Vacantes y postulaciones, reglas que D15 y D16 dejaban abiertas. Una vacante se genera hasta el inicio del turno; después ya no (las coberturas parciales están fuera de alcance, D29). La genera el titular, el asignado vigente o un coordinador; en un turno sin titular y sin asignado, solo un coordinador. La retira quien la generó o un coordinador mientras está abierta; si la había generado el asignado que se borró al abrirla (D31), el retiro lo restaura. Varias vacantes en una acción (lote) son todo o nada, hasta 31 turnos. Una vacante urgente avisa a los médicos con acceso ese día, salvo a quien la generó. Se postula a un turno con vacante abierta o sin titular (D24), hasta su inicio; un turno marcado sin cobertura (D19) ya empezó, así que solo se lo asigna. La postulación sobrevive a la asignación, pero la lista de candidatos no incluye al asignado actual ni a quien generó la vacante abierta (cancelar es decir que no puede). Vuelve a postularse quien se retiró reactivando la misma fila, con hora nueva (queda al final del desempate, D17). Se postula y se asigna solo a médicos: nunca coordinadores ni pendientes, y un dado de baja solo para turnos hasta su fecha de baja inclusive. El turno cuenta por su fecha de inicio (D13): quien tiene baja un día puede tomar la guardia que empieza ese día aunque termine al siguiente.
Alternativa descartada: permitir generar la vacante con el turno en curso. Motivo: sin coberturas parciales, un médico que se va a mitad de la guardia no tiene una vacante que se pueda cubrir; es un caso para el coordinador.
Motivo de la habilitación: D23 (el coordinador no cubre vacantes) y D24 (la cuenta de un médico de baja rige hasta su fecha).

D33. Asignación y candidatos, reglas que D17 y D18 dejaban abiertas. Solo los coordinadores ven los candidatos y asignan. Los no elegibles (D16) se listan al final con su motivo y no se pueden asignar; "el coordinador puede elegir a cualquier candidato" significa que no está obligado a elegir al primero. La asignación vale hasta el fin del turno (D19). Si el turno ya tiene asignado hay que pedir explícitamente `reasignar`, así dos coordinadores no se pisan. Asignar cierra la vacante abierta como CUBIERTA; si el turno estaba marcado sin cobertura, levanta la marca en la misma transacción. El asignado recibe una notificación. Las horas de la semana que informa la lista son las que el médico ya tiene en esa semana, sin contar el turno evaluado.
Alternativa descartada: dejar que el segundo coordinador reasigne sin avisarle que el turno ya tenía asignado. Motivo: la concurrencia se resuelve con restricciones y el cliente tiene que enterarse del conflicto (regla 8).

D34. Un turno en BAJA con postulantes se muestra en ámbar conservando la etiqueta BAJA, para que el coordinador vea que alguien quiere cubrirlo provisoriamente hasta designar un nuevo titular; toda tarjeta con postulantes indica cuántos. Ajusta D24, que mostraba en rojo toda guardia sin titular. La cantidad se calcula (postulaciones activas del turno, `cantidadPostulantes` en GET /turnos); no se guarda.
Origen: prueba de la app con un médico del servicio el 8/10/2026.

## Pendiente de confirmar

Sin pendientes al 4/10/2026.
