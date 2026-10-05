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
Resultado: spec en `docs/superpowers/specs/2026-10-05-f0-f1-esqueleto-plantilla-calendario-design.md` y plan en `docs/superpowers/plans/2026-10-05-f0-f1-esqueleto-plantilla-calendario.md`. Preguntas del agente antes del spec: herramienta de entorno de Python (venv + pip), autenticación en F1 (abierto hasta F5), granularidad de horarios (inicio HH:MM, duración en horas enteras). El agente señaló una inconsistencia en D10 (médico en el horario o en la versión), que se corrigió. Durante el diseño el equipo agregó el marcador commit_real para las pruebas de concurrencia de F3. Implementación por subagentes con Sonnet en la branch feature/esqueleto-calendario.

## Próximas entradas

Copiar acá el prompt con que arranca cada funcionalidad (F2 a F6) y cualquier prompt de corrección que haya cambiado el rumbo.
