# TP Final — Sistema de gestión de guardias médicas

**Grupo 7** — Ana María Florencia Lucca, Carlos Alejandro Lugones, Mariano Ezequiel Reimondez

Reemplazo del grupo de WhatsApp + planilla de Excel que hoy usa el servicio hospitalario
para gestionar guardias, por una aplicación (móvil + web) con calendario en tiempo real,
plantilla base de guardia, semáforo de vacantes (rojo/amarillo/verde) y notificaciones
push propias. Ver la especificación completa en
[`prompt_tp_final_v02.md`](prompt_tp_final_v02.md).

## Estado actual

**Etapa en curso: diseño de frontend.** Todavía no hay backend ni persistencia real —
el prototipo corre con datos de ejemplo en memoria, pensado para validar los flujos e
interacciones antes de definir el modelo de datos y la API.

Prototipo interactivo: **[Guardia Viva](https://claude.ai/artifact/3T56cETi81zUAJxqujU7hv)**

## Qué decidí yo

Resumen de las decisiones del equipo, agrupadas por tema. El detalle de cada una (alternativas, motivos y ajustes posteriores) está en [`docs/decisiones-arquitectura.md`](docs/decisiones-arquitectura.md), y cada decisión lleva su código (D01 a D31). Los hallazgos de las revisiones están completos en [`docs/bitacora-de-desvios.md`](docs/bitacora-de-desvios.md).

Dos marcas destacan de dónde salió el cambio:

- **[Validación]**: cambió al validar el modelo con Carlos, médico de guardia del servicio (4/10/2026). El diseño anterior suponía rotaciones, un coordinador que hace guardias y prioridad por descanso; nada de eso existe en el servicio real.
- **[Revisión]**: cambió por un hallazgo de la revisión de código de una branch completa, hecha por un subagente con contexto nuevo.

### Plataforma

- **D02. Persistencia en Supabase (Postgres).** Descartados: Google Drive o Sheets (sin transacciones ni unicidad) y SQLite (difícil de desplegar con datos persistentes en hostings gratuitos). Motivo: las restricciones únicas, los índices parciales y las restricciones de exclusión resuelven la concurrencia en la base.
- **D03. Backend en Python con FastAPI.** Descartados: Node con Express, y usar Supabase directo desde el frontend (sin servidor ni endpoints propios). Motivo: FastAPI genera el OpenAPI navegable en `/docs`, que es el contrato con la interfaz; Python es el lenguaje común de la maestría.
- **D04. SQLAlchemy y Alembic.** Motivo: estándar con FastAPI; cada cambio de esquema queda como migración numerada en el repositorio.
- **D05. React con Vite, PWA, servida por el backend.** Descartado: adaptar el prototipo HTML sin framework (menos trabajo, pero ordena peor varias pantallas y el estado que cambia con las notificaciones). Notificaciones dentro de la app con consulta periódica; se descartaron Web Push, push nativo y mail porque en iPhone exigen instalar la app y son frágiles en vivo.
- **D06. Supabase Auth con email y contraseña.** [Validación] Descartado: login con Google, que era el diseño anterior; el servicio usa usuario y contraseña, que además funciona con cualquier email. Las contraseñas nunca se guardan en tablas propias.
- **D30. Registro con código de coordinación.** Descartados: contraseñas temporales e invitaciones por mail (más trabajo y dependen del envío de mails). Motivo: es lo más simple y resuelve el alta del primer coordinador. Limitación reconocida: en producción se reemplazaría por invitaciones.
- **D07. RLS activado sin políticas.** Motivo: Supabase publica las tablas con la clave pública; sin RLS cualquiera podría saltear las reglas del backend.

### Modelo de dominio

- **D08. Modelo C5: turno materializado perezosamente, entidades operativas y bitácora mínima.** Descartados: C1 (plantilla + excepciones + snapshot: redundante y las rectificaciones sobrescriben), C1.5 (sin bitácora: pierde valores anteriores y el contexto de cada decisión) y C4 (bitácora completa: duplica las entidades y abre inconsistencias entre estado y bitácora).
- **D09. Identidad del turno = horario + fecha de inicio** (`horarioId:fecha`). Motivo: existe aunque el turno nunca se haya guardado y no cambia si cambia la plantilla.
- **D10. Horarios pactados versionados** (identidad estable + versiones con vigencia). Descartado: una sola tabla con vigencias, donde cada versión tiene otro identificador y deja colgadas las excepciones futuras. [Revisión] Una versión que todavía no rige se modifica en el lugar: sin ese ajuste, un médico con un horario cargado a futuro no podía darse de baja ni pasar a coordinador.
- **D11. Materialización perezosa.** Descartado: materializar los turnos de las próximas N semanas, que obliga a regenerar y reconciliar ante cada cambio de plantilla. El turno se guarda solo cuando se genera una vacante o se consolida (D12: un cambio de plantilla nunca rompe lo ya guardado).
- **D14. Frecuencia en semanas en lugar de rotación.** [Validación] Descartado: varios titulares rotativos por horario (entidad VersionTitular). Cada horario es de una sola persona y algunos médicos lo hacen semana por medio; dos médicos que se alternan son dos horarios de frecuencia 2 desfasados.
- **D23. Roles excluyentes: médico o coordinador.** [Validación] Descartado: coordinador que también hace guardias; en el servicio no cubre vacantes ni tiene horarios. Siempre queda al menos un coordinador activo, garantizado con bloqueos en la base.
- **D24. Baja sin borrar al usuario; el horario queda sin titular.** [Validación] Descartado: obligar a transferir o cerrar cada horario al dar de baja; el lugar tiene que verse como BAJA (en rojo) hasta que se designe a otra persona, y mientras tanto se cubre con el circuito habitual.

### Reglas operativas

- **D15. Una vacante por turno**, con carga de varias fechas en una acción para vacaciones y congresos. Motivo: cada turno se cubre por separado; las vacantes con menos de 24 h se marcan urgentes.
- **D16. Postulación al turno, no a la vacante.** Motivo: si el asignado cancela, los candidatos anteriores siguen activos como reserva para cancelaciones de último momento.
- **D17. Candidatos ordenados por equidad** (quien cubrió menos vacantes en el mes). [Validación] Descartado: ranking por horas de descanso con advertencia por menos de 12 h; en el servicio no hay prioridad por descanso y el médico propuso repartir la carga extra en forma pareja.
- **D18. Un solo endpoint de asignación** para elegir candidato, asignar directo o reasignar. Motivo: es la misma acción ("esta persona cubre este turno"); el backend distingue los casos para la bitácora.
- **D19. Turno sin cobertura con alertas a 48 h, 24 h y al inicio**, e indicador de horas sin cobertura por mes. [Validación] Hoy, cuando nadie cubre, los demás trabajan el doble y no queda registro; el indicador lo hace visible.
- **D20. Consolidación perezosa e idempotente.** Descartado: un proceso programado. Motivo: tolera caídas del servidor. [Revisión] Un cambio de plantilla que empieza hoy con el turno de hoy ya en curso responde 422 en lugar de guardar historia incorrecta.
- **D21. Rectificación con motivo obligatorio.** Descartado: sobrescribir el realizador (modelo C1). Motivo: queda un evento con el valor anterior.
- **D22. Bitácora solo de agregar, en la misma transacción que el cambio.** Descartado: registrar también consultas, logins y cambios de plantilla. Motivo: solo se registran acciones y lo que ninguna entidad conserva.
- **D25. Motivo de ausencia visible solo para coordinadores.** Motivo: puede incluir información personal o de salud.
- **D31. Generar una vacante borra al asignado en la misma transacción.** Descartado: conservar el asignado mientras la vacante está abierta; cada consulta tendría que acordarse de ignorarlo, y un olvido atribuiría la guardia a quien canceló.

### Alcance para el Demo Day

- **D26. Pantalla de staff completa para el coordinador** (activar, cargar y modificar horarios, cambiar rol, dar de baja, designar titular). Los datos de ejemplo se cargan por script, y el alta de usuarios es por registro (D30).
- **D27. Reloj de demo inyectable.** Motivo: mostrar consolidación y alertas sin esperar horas; las pruebas usan el mismo mecanismo. [Revisión] Descartado: guardar el desfase en memoria; volver a la hora real dejaba historia consolidada en el futuro, así que el desfase pasó a la base y el seed lo reinicia.
- **D28. Usuarios de demo cargados por seed y vinculados por email.** [Revisión] Descartado: vincular cualquier usuario cargado sin código; con la confirmación de email desactivada, cualquiera podía registrarse con el email del coordinador de ejemplo y quedar como coordinador. Vincular un coordinador cargado exige el código de coordinación.
- **D29. Fuera de alcance:** coberturas parciales, intercambios entre médicos, push nativo y mail. Motivo: el README evalúa la aplicación de punta a punta, no el canal de notificaciones (D05).

Otros hallazgos de revisión que no cambiaron una decisión, pero sí el código: carreras entre dar de baja y designar titular (F5), un deadlock posible en el cambio de rol (F5) y un médico dado de baja que quedaba como realizador presunto (F4). Los puntos menores que quedan pendientes también están en la bitácora.

## Historial de versiones

### v1 — Especificación funcional
Documento de partida (`prompt_tp_final_v02.md`) con el diseño completo del sistema:
- Dominio: equipo de 10-12 médicos, turnos de duración variable (6/7/8/12/24 h) que
  pueden cruzar la medianoche, superposición de turnos.
- Plantilla base de guardia (titular fijo por día/horario, con soporte para rotación
  entre dos o más titulares) como dato de fondo, distinto de la gestión de vacantes.
- Semáforo de tres estados (rojo/amarillo/verde) y regla de priorización de candidatos
  por horas de descanso desde la última guardia efectivamente realizada.
- Roles médico/coordinador con control de permisos doble (visual + servidor).
- Alta, baja e inactivación de médicos sin borrar historial.
- Notificaciones push propias de la app (se descartó WhatsApp Business API).
- Requisito de persistencia sobre un recurso de Google Drive (mecanismo concreto
  todavía abierto).
- Pendientes explícitos: diseño visual definitivo, modelo de datos completo, mecanismo
  técnico de push, y si hace falta un Data Warehouse.

### v2 — Primer prototipo de frontend interactivo ("Guardia Viva")
A partir de la v1, se construyó un prototipo funcional de la interfaz, con foco en
validar la experiencia antes de tocar backend:

- **Vista mensual** tipo Google Calendar/Apple Calendar, con indicador visual (punto
  rojo/amarillo) en los días con novedades, sin listar los turnos completos en el
  casillero del día.
- **Vista diaria** como línea de tiempo horizontal de 24 h, con una fila por turno,
  barras superpuestas coloreadas por estado, línea de "ahora", y control de **zoom**
  (+/−) para ajustar la densidad horaria — al estilo Google Calendar.
- **Transición mes → día**: tocar un día en la vista mensual "hace zoom" a su detalle,
  con botón para volver.
- **Simulador de tres roles en una sola pantalla**: paneles de Médico 1 (Valentina
  Ríos), Médico 2 (Martín Aguirre) y Coordinadora (Renata Ibarra), cada uno navegando
  su propio calendario de forma independiente pero compartiendo el mismo estado — una
  acción en un panel (generar vacante, postularse, confirmar) se refleja al instante
  en los otros dos, con un toast de aviso por panel y un feed de "Actividad en vivo"
  compartido arriba de todo. Simula el efecto de las notificaciones push en tiempo real
  sin necesidad de backend.
- **Flujos completos implementados**: generar vacante → postularse → confirmar
  candidato por el coordinador (con lista de candidatos ordenada por horas de descanso
  desde la última guardia, incluyendo el caso de médico sin guardias previas) → retirar
  postulación.
- **Datos de ejemplo**: 11 médicos, plantilla semanal con las 5 duraciones de turno de
  la consigna (6, 7, 8, 12, 24 h), turnos que cruzan la medianoche, y un caso de
  titular en rotación (jueves 08–16, alternando semana por medio) para probar ese
  mecanismo.
- **Fuera de alcance de esta versión** (a propósito, para no desviar el foco de
  frontend): alta/baja/inactivación de médicos, edición de la plantilla base desde la
  UI, y toda la persistencia — hoy es sólo estado en memoria del navegador.

## Próximos pasos

- Pulir diseño visual definitivo (colores, tipografía, disposición) sobre esta base.
- Definir el modelo de datos completo (entidades, atributos, relaciones), incluyendo
  cómo modelar la plantilla base y su relación con los turnos generados por excepción.
- Diseñar el contrato de API (siguiendo la misma lógica que el TP2 con OpenAPI).
- Definir el mecanismo técnico de notificaciones push (proveedor, payload, tokens).
- Resolver la implementación de persistencia sobre Google Drive y justificarla.
- Evaluar si el TP final requiere vincularse a un Data Warehouse.
