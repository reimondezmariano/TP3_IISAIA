# Prompts principales

Registro de los prompts que guiaron el trabajo: el que arranca cada funcionalidad y los de corrección importantes. Es la fuente de la sección "Prompts principales" del README.

Formato de cada entrada: fecha, herramienta, objetivo, prompt (completo o resumido si es muy largo), resultado.

## 1. Brainstorming de arquitectura

Fecha: 1 al 3/10/2026.
Herramientas: ChatGPT (primera ronda) y Claude (sesión de arquitectura, sin código).
Objetivo: analizar críticamente el modelo de dominio y de persistencia antes de implementar, comparar alternativas (C1, C1.5, C4) y terminar con una arquitectura defendible.
Prompt: ver `prompt_tp_final_v01.md` y `prompt_tp_final_v02.md` en la raíz del repo. Pedía actuar como arquitecto de software y compañero de brainstorming, no como implementador; cuestionar las decisiones del equipo; comparar modelos; resolver la identidad del turno virtual; analizar el modelo temporal, la consolidación y la bitácora; proponer un DER y probarlo contra 12 escenarios; y mostrar cada alternativa como opción, ventaja, costo y cuándo elegirla, dejando la decisión final al equipo.
Resultado: modelo C5 y las decisiones D01 a D28 en `docs/decisiones-arquitectura.md`. Se trabajó paso a paso (restricciones, reglas de dominio, modelo temporal, comparación de modelos, DER, API, persistencia), con una decisión del equipo en cada paso.

## 2. Validación con el usuario experto

Fecha: 4/10/2026.
Herramienta: preguntas generadas con Claude y respondidas por Carlos, médico de guardia.
Objetivo: confirmar supuestos del modelo con alguien que conoce el servicio real.
Prompt (preguntas enviadas):
1. ¿Los horarios de las guardias son fijos? ¿Qué franjas existen?
2. ¿Cómo se reparten: cada médico con un día fijo, rotaciones de varias semanas o un cuadrante mensual armado a mano?
3. ¿El coordinador también hace guardias y puede cubrir vacantes? Si se postula, ¿puede elegirse a sí mismo?
4. ¿Hay un descanso mínimo obligatorio después de una guardia?
5. Cuando nadie cubre, ¿qué se hace hoy en la práctica?
6. ¿Con cuánta anticipación suelen avisarse las ausencias?
Resultado: se eliminaron la rotación de titulares y el ranking por descanso; se agregaron la frecuencia semanal, el orden por equidad, el indicador de horas sin cobertura, el login con email y contraseña, el código de coordinación y la baja con horarios sin titular (D06, D14, D17, D19, D23 a D26, D30).

## 3. F0 y F1: esqueleto, plantilla y calendario

Fecha: 5/10/2026.
Herramienta: Claude Code con Superpowers (/brainstorming).
Prompt: ver la sección "Primer prompt (F0 + F1)" de `docs/plan-de-implementacion.md`, con las respuestas a preguntas técnicas agregadas al final.
Resultado: spec en `docs/superpowers/specs/2026-10-05-f0-f1-esqueleto-plantilla-calendario-design.md` y plan en `docs/superpowers/plans/2026-10-05-f0-f1-esqueleto-plantilla-calendario.md`. Preguntas del agente antes del spec: herramienta de entorno de Python (venv + pip), autenticación en F1 (abierto hasta F5), granularidad de horarios (inicio HH:MM, duración en horas enteras). El agente señaló una inconsistencia en D10 (médico en el horario o en la versión), que se corrigió. Durante el diseño el equipo agregó el marcador commit_real para las pruebas de concurrencia de F3. Implementación por subagentes con Sonnet en la branch feature/esqueleto-calendario, con revisión por tarea y revisión final; pull request #6.

## 4. F2: cimientos

Fecha: 7/10/2026.
Herramienta: Claude Code con Superpowers (writing-plans; sin brainstorming ni spec propio: el plan se apoya en las decisiones de arquitectura).
Prompt:

> Leé backend/CLAUDE.md y el documento de decisiones de arquitectura en docs. Vamos a hacer la fase F2 "cimientos": autenticación con Supabase Auth (D06, D07), POST /api/registro con código de coordinación (D30), GET /api/me, y los modelos Turno, Vacante, Postulacion, EventoTurno y Notificacion según D08 a D25, todos en una única migración de Alembic. No implementes reglas de negocio ni endpoints de vacantes o postulaciones: eso lo hace otro integrante. Usá Superpowers: escribí el plan en docs/superpowers/plans, trabajá en la branch feature/f2-cimientos y un commit por tarea. Por ahora solo escribí el plan, mostrámelo para aprobarlo y commitealo en la branch. No ejecutes ninguna tarea hasta que te lo pida.

Resultado: plan en `docs/superpowers/plans/2026-10-07-f2-cimientos.md`, con 13 decisiones que D06 a D30 dejaban abiertas (entre ellas, vencimiento del token con la hora real y vinculación por email de los usuarios del seed) para aprobar antes de ejecutar.
Corrección al aprobar el plan: "Agregá una tarea 6: que el script de datos de ejemplo conserve los vínculos con las cuentas de Supabase al volver a correrse." Se ejecuta en la misma sesión, con revisión de código de toda la branch antes del pull request.
Ejecución: "Ejecutá el plan de F2 cimientos." Seis tareas en la misma sesión con executing-plans, un commit por tarea, y revisión de toda la branch por un subagente. La revisión encontró que cualquiera podía tomar la cuenta de coordinador de Enzo sin el código (decisión 4 del plan combinada con D06); el equipo eligió exigir el código para vincular un coordinador cargado (cambio en D28). Corrección antes del pull request: "Antes del PR, corregí tres menores con su prueba y un commit cada uno: limitá ck_evento_alerta_umbral a '48H', '24H' e 'INICIO' dentro de la migración 0002; TOKEN_SIN_EMAIL responde 403 en lugar de 401; y anotá en la convención 8 de backend/CLAUDE.md que turno.creado_en es una marca técnica con DEFAULT now(). Los demás menores dejalos anotados en la bitácora de desvíos como pendientes." Pull request #7.

## 5. F3 (primera etapa): reglas de dominio puras

Fecha: 7/10/2026.
Herramienta: Claude Code con Superpowers (writing-plans y executing-plans).
Prompt: "Leé backend/CLAUDE.md y el documento de decisiones de arquitectura en docs, especialmente D15 a D22 y D27. En esta primera etapa implementá solo funciones puras en backend/app/dominio, sin base de datos y con pruebas pytest: elegibilidad de postulantes (D16), orden de candidatos por equidad (D17), consolidación (D20), umbrales de alerta 48 h, 24 h e inicio (D19) y vacante urgente (D15). No crees modelos ni migraciones: los está haciendo Florencia en feature/f2-cimientos. Usá Superpowers: plan en docs/superpowers/plans, branch feature/f3-reglas-dominio, un commit por tarea."
Resultado: plan en `docs/superpowers/plans/2026-10-07-f3-reglas-dominio-puras.md` y branch `feature/f3-reglas-dominio`, con un módulo por regla en `backend/app/dominio/` y sus pruebas. El plan lista los supuestos que cierran lo que las decisiones dejan abierto. Ejecución inline en una sola sesión, con revisión de toda la branch por un subagente. Tras la revisión: "Resolvimos con el equipo el supuesto 5 del plan" (la vacante abierta tiene prioridad sobre el asignado y el titular), que dio la decisión D31. Al traer main (PR #7) se alinearon los valores de `Umbral` con la restricción de la migración 0002. Pull request #8.

## 6. F5: staff, backend

Fecha: 7/10/2026.
Herramienta: Claude Code con Superpowers (writing-plans; sin brainstorming ni spec propio: el plan se apoya en las decisiones de arquitectura).
Prompt:

> Partí de la branch feature/f2-cimientos (todavía no está mergeada en main) y creá a partir de ella la branch feature/f5-staff-backend. Leé backend/CLAUDE.md y el documento de decisiones de arquitectura en docs, especialmente D10, D12, D23, D24 y D26. Vamos a hacer la fase F5 "staff, backend": endpoints solo para coordinadores para listar usuarios con rol, estado y horarios vigentes; activar un médico pendiente; cargar un horario pactado; modificarlo creando una nueva versión y devolviendo la lista de turnos afectados (D12); cerrar un horario; cambiar el rol respetando D23 (siempre al menos un coordinador activo, y un médico que pasa a coordinador deja antes sus horarios sin titular); dar de baja a un médico (D24: fecha de baja, sus horarios quedan sin titular con una versión nueva) y designar nuevo titular en un horario sin titular. Restricciones: no toques nada de vacantes, postulaciones ni consolidación, que son de Mariano. La parte de D24 que reabre como vacantes las coberturas aceptadas por el médico dado de baja tiene que usar la función de generar vacante de Mariano, que todavía no existe: dejala como última tarea del plan, marcada como dependiente. Si necesitás una migración, numerala a continuación de la de F2. Usá Superpowers: escribí el plan en docs/superpowers/plans y un commit por tarea. Solo escribí el plan, mostrámelo para aprobarlo y commitealo. No ejecutes nada hasta que te lo pida.

Resultado: plan en `docs/superpowers/plans/2026-10-07-f5-staff-backend.md`, con 11 tareas (la última, dependiente de F2b) y 16 decisiones, entre ellas una ambigüedad de D24 (fecha de baja como último día activo). El equipo aprobó las decisiones 1 a 7.
Ejecución: "Ejecutalo en esta sesión, tarea por tarea y un commit por tarea. La tarea 11 no la hagas hasta que la función de Mariano esté en main. Al terminar las tareas 1 a 10, hacé la revisión de código de toda la branch, con atención especial al orden de los bloqueos en el cambio de rol y en la baja." Tareas 1 a 10 con executing-plans; la 11 queda pendiente.

## Próximas entradas

Copiar acá el prompt con que arranca cada funcionalidad (F2 a F6) y cualquier prompt de corrección que haya cambiado el rumbo.
