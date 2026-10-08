# TP Final — Sistema de gestión de guardias médicas

**Grupo 7** — Ana María Florencia Lucca, Carlos Alejandro Lugones, Mariano Ezequiel Reimondez

Guardia Viva reemplaza el grupo de WhatsApp y la planilla Excel con que un servicio
hospitalario de 10 a 12 médicos gestiona sus guardias. Es una aplicación web responsive,
pensada para instalarse en el celular, con un calendario compartido calculado desde los
horarios pactados de cada médico, vacantes y postulaciones para cubrir ausencias, un
semáforo que muestra qué turnos están en riesgo, y notificaciones dentro de la app (las
vacantes urgentes se muestran además como aviso emergente). El diseño está en
[`CLAUDE.md`](CLAUDE.md); el documento de partida, en
[`prompt_tp_final_v02.md`](prompt_tp_final_v02.md).

## Estado actual

**Etapa en curso: funcionalidades de coordinación e interfaz (F3 a F6), con miras al Demo Day del 14/10/2026.**

Aplicación publicada: **PENDIENTE: dirección publicada en Render** <!-- Reemplazar por la URL de Render -->

Arquitectura (detalle en [`CLAUDE.md`](CLAUDE.md) y [`docs/decisiones-arquitectura.md`](docs/decisiones-arquitectura.md)):

- **Backend** en [`backend/`](backend/): Python con FastAPI, SQLAlchemy y Alembic. Expone la API bajo `/api`, con el contrato OpenAPI navegable en `/docs`.
- **Base de datos** en Supabase (Postgres), con RLS activado sin políticas; el backend se conecta con credenciales propias. La concurrencia se resuelve con restricciones de la base.
- **Autenticación** con Supabase Auth (email y contraseña) y registro con código de coordinación.
- **Frontend** en [`frontend/`](frontend/): React con Vite, web responsive pensada para instalarse en el celular (PWA). En producción el backend sirve la compilación, así que hay un solo despliegue.
- **Despliegue** en Render, con redespliegue en cada merge a `main` (ver [`docs/despliegue.md`](docs/despliegue.md)).

Qué funciona hoy:

- Registro, login, activación de médicos pendientes y `GET /api/me`.
- Plantilla de horarios pactados versionados y calendario calculado (`GET /api/turnos`).
- Generar vacantes (de a una o en lote) y retirarlas.
- Consolidación de turnos terminados, turno sin cobertura, alertas escalonadas, notificaciones, indicador de horas sin cobertura y reloj de demo.
- API de staff: usuarios, horarios, baja de médicos y cambio de rol, con reapertura de las coberturas aceptadas.
- Interfaz del médico: login, registro y calendario semanal.

Todavía no:

- Postulaciones, candidatos y asignación responden datos de ejemplo (encabezado `X-Respuesta-Ejemplo: true`); la lógica real está en curso.
- Rectificación y detalle del turno (`GET /api/turnos/{turnoId}`).
- En la interfaz, las vacantes todavía se simulan en el navegador; faltan las pantallas del coordinador (candidatos, staff), el aviso emergente y el manifiesto de la PWA.

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

- **D15. Una vacante por turno.** Motivo: cada turno puede cubrirlo una persona distinta, así que una ausencia de varios días son vacantes independientes; para vacaciones y congresos la interfaz permite marcar varias fechas en una sola acción. Las vacantes con menos de 24 h se marcan urgentes para que las vea todo el servicio.
- **D16. Postulación al turno, no a la vacante.** Motivo: si el asignado cancela, los candidatos anteriores siguen activos como reserva para cancelaciones de último momento.
- **D17. Candidatos ordenados por equidad** (quien cubrió menos vacantes en el mes). [Validación] Descartado: ranking por horas de descanso con advertencia por menos de 12 h; en el servicio no hay prioridad por descanso y el médico propuso repartir la carga extra en forma pareja.
- **D18. Un solo endpoint de asignación** para elegir candidato, asignar directo o reasignar. Motivo: es la misma acción ("esta persona cubre este turno"); el backend distingue los casos para la bitácora.
- **D19. Turno sin cobertura con alertas a 48 h, 24 h y al inicio**, e indicador de horas sin cobertura por mes. [Validación] Hoy, cuando nadie cubre, los demás trabajan el doble y no queda registro; el indicador lo hace visible.
- **D20. Consolidación perezosa e idempotente.** Descartado: un proceso programado. Motivo: tolera caídas del servidor. [Revisión] Un cambio de plantilla que empieza hoy con el turno de hoy ya en curso responde 422 en lugar de guardar historia incorrecta.
- **D21. Rectificación con motivo obligatorio.** Descartado: sobrescribir el realizador (modelo C1). Motivo: queda un evento con el valor anterior.
- **D22. Bitácora solo de agregar, en la misma transacción que el cambio.** Descartado: registrar también consultas, logins y cambios de plantilla. Motivo: se registran solo acciones y lo que ninguna entidad conserva, y siempre en la misma transacción que el cambio, para que la bitácora nunca quede distinta del estado (por eso se descartó el modelo C4).
- **D25. Motivo de ausencia visible solo para coordinadores.** Motivo: puede incluir información personal o de salud.
- **D31. Generar una vacante borra al asignado en la misma transacción.** Descartado: conservar el asignado mientras la vacante está abierta; cada consulta tendría que acordarse de ignorarlo, y un olvido atribuiría la guardia a quien canceló.

### Alcance para el Demo Day

- **D26. Pantalla de staff completa para el coordinador** (activar, cargar y modificar horarios, cambiar rol, dar de baja, designar titular). Los datos de ejemplo se cargan por script, y el alta de usuarios es por registro (D30).
- **D27. Reloj de demo inyectable.** Motivo: mostrar consolidación y alertas sin esperar horas; las pruebas usan el mismo mecanismo. [Revisión] Descartado: guardar el desfase en memoria; volver a la hora real dejaba historia consolidada en el futuro, así que el desfase pasó a la base y el seed lo reinicia.
- **D28. Usuarios de demo cargados por seed y vinculados por email.** [Revisión] Descartado: vincular cualquier usuario cargado sin código; con la confirmación de email desactivada, cualquiera podía registrarse con el email del coordinador de ejemplo y quedar como coordinador. Vincular un coordinador cargado exige el código de coordinación.
- **D29. Fuera de alcance:** coberturas parciales, intercambios entre médicos, push nativo y mail. Motivo: coberturas parciales e intercambios directos quedan afuera por el plazo y por el criterio del modelo más simple: en el servicio cada horario es de un solo médico y se cubre completo. Push nativo y mail quedan afuera porque el README evalúa la aplicación de punta a punta, no el canal de notificaciones (D05).

Otros hallazgos de revisión que no cambiaron una decisión, pero sí el código: carreras entre dar de baja y designar titular (F5), un deadlock posible en el cambio de rol (F5) y un médico dado de baja que quedaba como realizador presunto (F4). Los puntos menores que quedan pendientes también están en la bitácora.

## Historial de versiones

### v1. Especificación funcional

Documento de partida ([`prompt_tp_final_v02.md`](prompt_tp_final_v02.md)): equipo de 10 a 12 médicos, turnos de duración variable que pueden cruzar la medianoche, plantilla base de guardia, semáforo de vacantes, roles médico y coordinador, y notificaciones propias de la app. Pedía persistir sobre un recurso de Google Drive, con el mecanismo todavía abierto.

### v2. Prototipo de interfaz en HTML ("Guardia Viva")

Prototipo interactivo, solo con datos en memoria del navegador, para validar los flujos antes de definir el modelo: vista mensual con indicadores, vista diaria como línea de tiempo de 24 h con zoom, y un simulador de tres roles (dos médicos y una coordinadora) en una sola pantalla que compartían el estado. Implementaba generar vacante, postularse, confirmar candidato y retirar postulación.

Prototipo: **[Guardia Viva](https://claude.ai/artifact/3T56cETi81zUAJxqujU7hv)**. Hoy es solo referencia visual: el frontend actual no reutiliza su código (D05).

Lo que cambió después de esta versión: Google Drive se reemplazó por Supabase (D02); la rotación de titulares, el coordinador que hace guardias y el orden de candidatos por descanso se eliminaron al validar con un médico del servicio (ver "Qué decidí yo").

### v3. Arquitectura y validación (1 al 4 de octubre de 2026)

| PR | Etapa |
|---|---|
| [#1](https://github.com/reimondezmariano/TP3_IISAIA/pull/1) | Documentos de arquitectura en `docs/` (decisiones D01 a D28 del brainstorming) |
| [#2](https://github.com/reimondezmariano/TP3_IISAIA/pull/2) | Ajustes al modelo tras validar con Carlos, médico del servicio |
| [#3](https://github.com/reimondezmariano/TP3_IISAIA/pull/3) | Bitácora de desvíos |
| [#4](https://github.com/reimondezmariano/TP3_IISAIA/pull/4) | Cierre de la planificación: frontend React, staff, código de coordinación, guion y prompts |
| [#5](https://github.com/reimondezmariano/TP3_IISAIA/pull/5) | Guion del Demo Day |

### v4. Implementación (desde el 5 de octubre de 2026)

Cada funcionalidad sigue el flujo de Superpowers (spec, plan, implementación por subagentes, revisión de código) en su propia branch; los planes están en [`docs/superpowers/plans`](docs/superpowers/plans).

| PR | Etapa |
|---|---|
| [#6](https://github.com/reimondezmariano/TP3_IISAIA/pull/6) | F0 y F1: esqueleto, plantilla y calendario calculado |
| [#7](https://github.com/reimondezmariano/TP3_IISAIA/pull/7) | F2: cimientos (Supabase Auth, registro, `GET /me` y modelo operativo) |
| [#8](https://github.com/reimondezmariano/TP3_IISAIA/pull/8) | F3, primera etapa: reglas de dominio puras |
| [#10](https://github.com/reimondezmariano/TP3_IISAIA/pull/10) | F5: staff, backend (usuarios, horarios, baja y cambio de rol) |
| [#9](https://github.com/reimondezmariano/TP3_IISAIA/pull/9) | F4: frontend del médico (login, registro y calendario semanal) |
| [#11](https://github.com/reimondezmariano/TP3_IISAIA/pull/11) | F3, etapa 1: contrato de vacantes, postulaciones y asignación con respuestas de ejemplo |
| [#12](https://github.com/reimondezmariano/TP3_IISAIA/pull/12) | F4: historia y alertas, backend (consolidación, sin cobertura, alertas, notificaciones, indicador y reloj de demo) |
| [#13](https://github.com/reimondezmariano/TP3_IISAIA/pull/13) | F3, etapa 2: generar vacante, lote y retiro |
| [#14](https://github.com/reimondezmariano/TP3_IISAIA/pull/14) | Despliegue: un solo servicio en Render con la compilación del frontend |
| [#15](https://github.com/reimondezmariano/TP3_IISAIA/pull/15) | F5, tarea 11: la baja y el cambio a coordinador reabren las coberturas aceptadas |

## Próximos pasos

1. F3: postulaciones, candidatos ordenados por equidad (D17) y asignación con lógica real, reemplazando las respuestas de ejemplo.
2. F4: rectificación y detalle del turno con su línea de tiempo.
3. F6: conectar las vacantes de la interfaz a la API, pantallas del coordinador (candidatos, staff, indicador), aviso emergente de vacantes urgentes y manifiesto de la PWA.
4. Aplicar las migraciones a Supabase desde `main` y publicar la dirección de Render en este README.
5. Cierre: pruebas en celulares, README final y ensayo de la demo con el script de reinicio (12 y 13/10).
