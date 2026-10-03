# Guardia Viva: decisiones de arquitectura

Registro de las decisiones tomadas durante el brainstorming de arquitectura (2 y 3 de octubre de 2026). Cada decisión indica las alternativas consideradas y el motivo de la elección. Este documento es la fuente de la sección "Qué decidí yo" del README.

Equipo: Carlos Lugones, Mariano Reimondez, Florencia Lucca.

## Contexto

Un servicio hospitalario de 10 a 12 médicos gestiona hoy sus guardias con un grupo de WhatsApp y una planilla Excel que actualiza el coordinador. Guardia Viva reemplaza ese mecanismo con una aplicación web instalable en el celular, un backend con API y persistencia.

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

D05. Interfaz web responsive instalable en el celular (PWA). Notificaciones dentro de la app, consultadas cada 10 a 15 segundos. Push nativo y Web Push quedan como trabajo futuro.
Motivo: el README evalúa la aplicación de punta a punta, no el canal de notificaciones. Web Push en iPhone exige instalar la app y es frágil en vivo.

D06. Autenticación con Supabase Auth (cuenta de Google). El backend verifica el token y busca al médico por email. Los permisos se validan en el backend aunque la interfaz oculte las acciones.

D07. Seguridad por filas (RLS) activada en todas las tablas, sin políticas. El frontend usa Supabase solo para el login; el backend se conecta a Postgres con credenciales propias.
Motivo: Supabase publica las tablas en una API accesible con la clave pública; sin RLS cualquiera podría saltear las reglas del backend.

## Modelo de dominio

D08. Modelo C5: turno materializado perezosamente, entidades operativas y bitácora mínima.
Alternativas analizadas:

| Modelo | Descripción | Por qué no |
|---|---|---|
| C1 | Plantilla + excepciones + snapshot GuardiaRealizada | Redundancia entre turno y snapshot; las rectificaciones sobrescriben; las decisiones del coordinador no quedan registradas |
| C1.5 | Entidades ricas con fechas y responsables, sin bitácora | Pierde valores anteriores en rectificaciones y reasignaciones, y la posición en el ranking al momento de elegir |
| C4 | C1.5 + bitácora de eventos completa | Duplica las entidades y abre la puerta a inconsistencias entre estado y bitácora |
| C5 (elegido) | C4 depurado | |

Diferencias de C5:
1. Turno y guardia realizada son la misma fila en distintos momentos.
2. La postulación se hace al turno, no a la vacante.
3. El semáforo se calcula, no se guarda.
4. No existe una tabla Asignacion: el turno guarda el asignado actual y la bitácora conserva los anteriores.
5. La bitácora registra solo acciones y solo lo que ninguna entidad conserva.

D09. Identidad del turno = casillero estable + fecha de inicio. En la API, identificador compuesto "casilleroId:fecha" (por ejemplo, 7:2026-10-10). Existe aunque el turno nunca se haya guardado y no cambia aunque cambie la plantilla.

D10. Versionado de la plantilla: Casillero (identidad estable) y VersionCasillero (horario, titulares, rotación, vigenteDesde, vigenteHasta). Un cambio cierra la versión vigente y abre otra. Las vigencias de un casillero no se superponen (restricción de exclusión de Postgres).
Alternativa descartada: una sola tabla con vigencias, donde cada versión tiene otro identificador y deja colgadas las excepciones futuras.

D11. Materialización perezosa: el turno se calcula desde la plantilla mientras no le pasa nada. Se guarda como fila cuando se genera una vacante o cuando se consolida. Al crearse copia inicio, fin, versión y titular planificado, que no se recalculan. Restricción única sobre (casillero, fecha).
Alternativa descartada: materializar todos los turnos de las próximas N semanas (obliga a regenerar y reconciliar ante cada cambio de plantilla).

D12. Un cambio de plantilla nunca rompe lo ya asignado. Las excepciones existentes conservan su snapshot y el coordinador recibe la lista de turnos afectados.

D13. Horario del casillero expresado como hora de inicio + duración. El turno pertenece a la fecha en que empieza. Zona horaria America/Argentina/Buenos_Aires; instantes guardados con zona horaria.

D14. Rotación por ciclo: lista ordenada de titulares, período en semanas y fecha ancla (un lunes). Titular de una fecha = posición (períodos transcurridos desde el ancla) módulo cantidad de titulares. Con un solo titular la fórmula da siempre él. La semana empieza el lunes.

## Reglas operativas

D15. Vacantes. Las genera el titular, el asignado o un coordinador. Cada vacante corresponde a un solo turno; una ausencia de varios días son varias vacantes independientes (la interfaz permite marcar varias fechas en una acción). El titular puede retirar la vacante mientras no haya asignación. Como máximo una vacante abierta por turno.

D16. Postulaciones al turno. La oferta de un médico vale para el turno mientras no ocurra y no la retire. Si el asignado cancela y se abre otra vacante, los candidatos anteriores siguen activos: son la reserva para cancelaciones de último momento y reciben una notificación para retirarse si ya no pueden. No se postula el titular a su propio turno ni un médico con una guardia superpuesta.

D17. Ranking de candidatos (apoyo a la decisión, no obligatorio):
1. Descanso previo = inicio del turno menos el fin de la última guardia del candidato que termine antes, sea realizada o asignada a futuro.
2. Sin guardias previas: primero.
3. Desempate: hora de postulación según el servidor.
4. Advertencia visible si el descanso previo es menor a 12 h; el candidato baja en el ranking pero no se excluye (sujeto a confirmación con Carlos).
5. Horas de guardia de los últimos 7 días como dato informativo.
6. La elegibilidad se calcula al consultar; si un impedimento desaparece, el candidato vuelve a ser elegible.

D18. Asignación con un solo endpoint. "Esta persona cubre este turno" cubre tres casos que el backend distingue: elección de un candidato, asignación directa de alguien que no se postuló, y reasignación. El coordinador puede elegir a cualquiera, no solo al primero.

D19. Turno descubierto. Si una vacante sigue abierta al llegar el inicio, el turno queda descubierto y el coordinador lo resuelve. Alertas escalonadas a los coordinadores a las 48 h, a las 24 h y al inicio, una sola vez por turno y umbral.

D20. Consolidación perezosa e idempotente. Antes de responder consultas de calendario o ranking, el backend consolida los turnos terminados; el coordinador también puede forzarla. Al terminar un turno cubierto, se presume realizado por el asignado vigente (o el titular). Tolera caídas del servidor porque no depende de un proceso programado.

D21. Rectificación. El coordinador corrige quién realizó una guardia consolidada, con motivo obligatorio. Queda un evento con el valor anterior. El ranking usa siempre el realizador vigente.

D22. Bitácora (EventoTurno) solo de agregar, escrita en la misma transacción que el cambio. Distingue actor humano y sistema. Eventos: VACANTE_GENERADA, VACANTE_RETIRADA, POSTULACION_CREADA, POSTULACION_RETIRADA, CANDIDATO_ELEGIDO (con posición en el ranking, descanso y cantidad de candidatos), ASIGNACION_DIRECTA, REASIGNACION, REALIZADOR_RECTIFICADO, ALERTA_SIN_COBERTURA. Excluidos: consolidación normal (ya está en consolidadoEn), consultas, logins, lecturas de notificaciones y cambios de plantilla (las versiones ya son su historia).

D23. Roles. Coordinador es un atributo del médico; puede haber varios y el rol puede cambiar de persona. El coordinador también es médico de guardia.

D24. Baja definitiva de un médico: fecha de baja (activo hasta ese día inclusive). En el mismo paso el coordinador designa reemplazante por casillero y el sistema crea la nueva versión de la plantilla. Si no hay reemplazante, los casilleros quedan marcados como "titular dado de baja" y el coordinador decide guardia por guardia. No se generan vacantes automáticas y nunca se borra al médico.

## Alcance para el Demo Day

D25. Plantilla: API completa, datos de ejemplo cargados por script, pantalla de lectura y formulario simple de nueva versión. La edición completa queda como trabajo futuro.

D26. Reloj de demo: en modo demo (variable de entorno) un endpoint adelanta la hora del sistema para mostrar consolidación y alertas. Las pruebas usan el mismo mecanismo. No existe fuera del modo demo.

D27. Demo: un usuario coordinador "Enzo" con una cuenta de Gmail creada por el equipo; los tres integrantes actúan como médicos postulantes desde sus celulares. Si Enzo quiere operar en vivo, se agrega su email. Plan de respaldo: todo desde una computadora.

D28. Fuera de alcance: coberturas parciales, intercambios directos entre médicos, reglas de descanso mínimo obligatorio, push nativo.

## Pendientes de confirmar con Carlos

1. ¿Los horarios de las guardias son fijos? ¿Qué franjas existen?
2. ¿Cómo se reparten: día fijo, rotación de varias semanas o cuadrante mensual armado a mano? (Un cuadrante sin ciclo obligaría a revisar D14).
3. Si el coordinador se postula, ¿puede elegirse a sí mismo?
4. ¿Hay descanso mínimo obligatorio después de una guardia? (Si lo hay, D17 pasa a excluir en lugar de advertir).
5. Cuando nadie cubre, ¿qué se hace hoy?
6. ¿Con cuánta anticipación se avisan las ausencias? (Ajusta los umbrales de D19).
