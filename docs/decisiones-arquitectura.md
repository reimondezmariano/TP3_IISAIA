# Guardia Viva: decisiones de arquitectura

Registro de las decisiones tomadas durante el brainstorming de arquitectura (2 y 3 de octubre de 2026) y de los ajustes tras validar el modelo con un médico del servicio (4 de octubre de 2026). Cada decisión indica las alternativas consideradas y el motivo de la elección. Este documento es la fuente de la sección "Qué decidí yo" del README.

Equipo: Carlos Lugones, Mariano Reimondez, Florencia Lucca.

## Contexto

Un servicio hospitalario de 10 a 12 médicos gestiona hoy sus guardias con un grupo de WhatsApp y una planilla Excel que actualiza el coordinador. Guardia Viva reemplaza ese mecanismo con una aplicación web instalable en el celular, un backend con API y persistencia.

Cómo funciona el servicio (validado con Carlos, médico de guardia):
1. Cada médico, al ingresar, pacta sus días y horarios, que se repiten todas las semanas. La duración varía según el médico: 6, 7, 8, 12 o 24 horas. No hay rotaciones.
2. Los médicos no trabajan todos los días: muchos hacen uno o dos días por semana, y cada uno decide su carga. No hay prioridad por descanso ni descanso mínimo obligatorio.
3. El coordinador no hace guardias ni cubre vacantes.
4. Cuando nadie cubre una ausencia, no se hace nada: los demás médicos trabajan el doble.
5. Las ausencias se avisan con anticipación muy variable: meses (vacaciones, congresos) o minutos (una urgencia familiar).

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

D05. Interfaz web responsive instalable en el celular (PWA). Notificaciones dentro de la app, consultadas cada 10 a 15 segundos. Push nativo y Web Push quedan como trabajo futuro. Mail para vacantes urgentes: trabajo futuro (a confirmar el 4/10).
Motivo: el README evalúa la aplicación de punta a punta, no el canal de notificaciones. Web Push en iPhone exige instalar la app y es frágil en vivo.

D06. Autenticación con Supabase Auth (cuenta de Google). El backend verifica el token y busca al usuario por email. Los permisos se validan en el backend aunque la interfaz oculte las acciones.

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

D10. Plantilla como horarios pactados versionados: HorarioPactado (identidad estable, pertenece a un médico) y VersionHorario (día de la semana, hora de inicio, duración, vigenteDesde, vigenteHasta). Una renegociación cierra la versión vigente y abre otra. Las vigencias de un horario no se superponen (restricción de exclusión de Postgres). Que horarios de distintos médicos se superpongan es normal: hay varios médicos de guardia a la vez.
Alternativa descartada: una sola tabla con vigencias, donde cada versión tiene otro identificador y deja colgadas las excepciones futuras.

D11. Materialización perezosa: el turno se calcula desde la plantilla mientras no le pasa nada. Se guarda como fila cuando se genera una vacante o cuando se consolida. Al crearse copia inicio, fin, versión y médico titular, que no se recalculan. Restricción única sobre (horario, fecha).
Alternativa descartada: materializar todos los turnos de las próximas N semanas (obliga a regenerar y reconciliar ante cada cambio de plantilla).

D12. Un cambio de plantilla nunca rompe lo ya asignado. Las excepciones existentes conservan su snapshot y el coordinador recibe la lista de turnos afectados.

D13. Horario expresado como hora de inicio + duración. El turno pertenece a la fecha en que empieza. Zona horaria America/Argentina/Buenos_Aires; instantes guardados con zona horaria. La semana empieza el lunes.

D14. Sin rotaciones: cada horario pactado tiene un solo médico, que se repite todas las semanas (a confirmar el 4/10).
Cambio tras validar con Carlos: el diseño anterior soportaba titulares rotativos con período y fecha ancla. Carlos confirmó que en el servicio no existen rotaciones; se eliminaron la rotación y la entidad VersionTitular.

## Reglas operativas

D15. Vacantes. Las genera el médico titular o asignado del turno, o un coordinador. Cada vacante corresponde a un solo turno; una ausencia de varios días son varias vacantes independientes (la interfaz permite marcar varias fechas en una acción, útil para vacaciones y congresos). El titular puede retirar la vacante mientras no haya asignación. Como máximo una vacante abierta por turno. Una vacante generada con menos de 24 h de anticipación se marca como urgente y se destaca para todos.

D16. Postulaciones al turno. La oferta de un médico vale para el turno mientras no ocurra y no la retire. Si el asignado cancela y se abre otra vacante, los candidatos anteriores siguen activos: son la reserva para cancelaciones de último momento y reciben una notificación para retirarse si ya no pueden. No se postula el titular a su propio turno ni un médico con una guardia superpuesta. La elegibilidad se calcula al consultar: si un impedimento desaparece, el candidato vuelve a ser elegible.

D17. Candidatos ordenados por hora de postulación (según el servidor), con datos informativos que no alteran el orden: horas de guardia del médico en esa semana y vacantes que cubrió en el mes (a confirmar el 4/10).
Cambio tras validar con Carlos: el diseño anterior ordenaba por horas de descanso previo, con advertencia por menos de 12 h. Carlos explicó que en el servicio no existe prioridad por descanso: los médicos hacen uno o dos días por semana y cada uno decide su carga. Se eliminaron el ranking por descanso y la advertencia.
Alternativa en estudio: ordenar por equidad (primero quien cubrió menos vacantes en el mes), si Carlos confirma que es una preocupación real.

D18. Asignación con un solo endpoint. "Esta persona cubre este turno" cubre tres casos que el backend distingue: elección de un candidato, asignación directa de alguien que no se postuló, y reasignación. El coordinador puede elegir a cualquier candidato.

D19. Turno sin cobertura. Alertas escalonadas a los coordinadores a las 48 h, a las 24 h y al inicio, una sola vez por turno y umbral. Si al llegar el inicio la vacante sigue abierta, el coordinador asigna a alguien o marca el turno como "sin cobertura". Se consolida sin realizador.
Indicador para el coordinador: horas sin cobertura por mes. Hoy, cuando nadie cubre, los demás médicos trabajan el doble y el problema no queda registrado; el indicador lo hace visible.

D20. Consolidación perezosa e idempotente. Antes de responder consultas de calendario, el backend consolida los turnos terminados; el coordinador también puede forzarla. Al terminar un turno cubierto, se presume realizado por el asignado vigente (o el titular). Tolera caídas del servidor porque no depende de un proceso programado.

D21. Rectificación. El coordinador corrige quién realizó una guardia consolidada, con motivo obligatorio. Queda un evento con el valor anterior.

D22. Bitácora (EventoTurno) solo de agregar, escrita en la misma transacción que el cambio. Distingue actor humano y sistema. Eventos: VACANTE_GENERADA, VACANTE_RETIRADA, POSTULACION_CREADA, POSTULACION_RETIRADA, CANDIDATO_ELEGIDO (con la posición en la lista y la cantidad de candidatos), ASIGNACION_DIRECTA, REASIGNACION, TURNO_SIN_COBERTURA, REALIZADOR_RECTIFICADO, ALERTA_SIN_COBERTURA. Excluidos: consolidación normal (ya está en consolidadoEn), consultas, logins, lecturas de notificaciones y cambios de plantilla (las versiones ya son su historia).

D23. Roles excluyentes: cada usuario es MEDICO o COORDINADOR. El coordinador no tiene horarios pactados, no se postula y no cubre vacantes. El rol puede cambiar de persona y puede haber varios coordinadores (lectura a confirmar con Carlos).
Cambio tras validar con Carlos: el diseño anterior suponía que el coordinador también era médico de guardia.

D24. Baja definitiva de un médico: fecha de baja (activo hasta ese día inclusive). En el mismo paso, el coordinador decide para cada horario pactado si lo transfiere a otro médico (nueva versión) o lo cierra (el servicio pierde esas horas). Las coberturas que el médico había aceptado para turnos posteriores se le listan al coordinador para reabrirlas. Nunca se borra un usuario.

D25. Motivo de la ausencia opcional y visible solo para el coordinador.
Motivo: puede incluir información personal o de salud que no corresponde mostrar a todo el servicio.

## Alcance para el Demo Day

D26. Plantilla: API completa, datos de ejemplo cargados por script, pantalla de lectura y formulario simple de nueva versión. La edición completa queda como trabajo futuro.

D27. Reloj de demo: en modo demo (variable de entorno) un endpoint adelanta la hora del sistema para mostrar consolidación y alertas. Las pruebas usan el mismo mecanismo. No existe fuera del modo demo.

D28. Demo: un usuario coordinador "Enzo" con una cuenta de Gmail creada por el equipo; los tres integrantes actúan como médicos desde sus celulares. Si Enzo quiere operar en vivo, se agrega su email. Plan de respaldo: todo desde una computadora.

D29. Fuera de alcance: coberturas parciales, intercambios directos entre médicos, rotaciones, push nativo.

## Pendiente de confirmar (reunión del 4/10, 17:00)

1. D14: eliminar la rotación.
2. D17: orden por hora de postulación con datos informativos, o por equidad de coberturas.
3. D05: mail para vacantes urgentes ahora o como trabajo futuro.
4. D23: confirmar con Carlos que el coordinador no hace guardias.
