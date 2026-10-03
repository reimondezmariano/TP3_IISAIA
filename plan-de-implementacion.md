# Guardia Viva: cómo pasamos a Claude Code

## Preparación (una sola vez)

1. Clonar el repo de Mariano. Mariano suma a Carlos y Florencia como colaboradores y le avisa a Enzo por mail cuál es el repo del TP.
2. Copiar a la raíz del repo `CLAUDE.md` y la carpeta `docs/` con `decisiones-arquitectura.md` y este archivo. Primer commit en main.
3. Crear el proyecto en Supabase (región São Paulo, la más cercana) y la cuenta de Gmail del coordinador de la demo.
4. En Claude Code, instalar los plugins y herramientas que mostró Enzo:
   1. `/plugin install superpowers@claude-plugins-official`. Si no lo encuentra, agregar antes el marketplace que mostró Enzo con `/plugin marketplace add obra/superpowers-marketplace` y volver a instalar. Verificar con `/plugin list`.
   2. Playwright MCP, para que el agente pruebe la interfaz por su cuenta: desde la terminal, `claude mcp add playwright npx @playwright/mcp@latest`.
5. Abrir la sesión parados en la raíz del repo y verificar con `/context` que cargó el CLAUDE.md.

## Orden de funcionalidades

Cada funcionalidad es un ciclo completo de Superpowers: brainstorming, spec, plan, implementación por subagentes, revisión y pull request. Cada ciclo arranca en una sesión nueva.

| # | Funcionalidad | Contenido | Fecha objetivo |
|---|---|---|---|
| F0 | Esqueleto | Estructura de carpetas, FastAPI, conexión a Supabase, Alembic, pytest, reloj inyectable, CLAUDE.md de backend y frontend | 5/10 |
| F1 | Plantilla y calendario | Medico, Casillero, VersionCasillero, VersionTitular, rotación, GET /turnos calculado, script de datos de ejemplo | 6/10 |
| F2 | Vacantes y postulaciones | Turno materializado, Vacante, Postulacion, semáforo calculado, reglas de elegibilidad, bitácora | 7/10 |
| F3 | Ranking y asignación | Cálculo de descanso, advertencia de 12 h, PUT asignacion con sus tres casos, pruebas de concurrencia | 8/10 |
| F4 | Historia y alertas | Consolidación perezosa, rectificación, alertas escalonadas, notificaciones, reloj de demo | 9/10 |
| F5 | Seguridad y médicos | Supabase Auth, roles, RLS, baja con reemplazante | 9/10 |
| F6 | Interfaz y despliegue | Conectar el prototipo a la API, PWA, despliegue | 10 y 11/10 |
| Cierre | Ensayo | Pruebas en celulares, README final, ensayo de la demo con el script de reinicio | 12 y 13/10 |

## Consumo de tokens

1. Las sesiones de implementación las lleva quien tenga plan pago.
2. Pedir que los subagentes que implementan usen Sonnet o Haiku y que las revisiones usen Sonnet.
3. Para ajustes chicos (un texto, un color, un campo), no usar el flujo completo.

## Evidencia para el README (anotar sobre la marcha)

1. "Cómo gestioné el contexto": CLAUDE.md por nivel, documento de decisiones, una sesión por funcionalidad, subagentes, specs y planes en disco.
2. "Qué salió mal": cada vez que el agente se desvíe o una revisión encuentre un error, anotar en `docs/bitacora-de-desvios.md` qué pasó, cómo se detectó y cómo se corrigió. Al final se resume.

## Primer prompt (F0 + F1)

Pegar en una sesión nueva de Claude Code, parados en la raíz del repo:

```
/brainstorming Vamos a construir el backend de Guardia Viva. El brainstorming de arquitectura ya está hecho y sus decisiones están en docs/decisiones-arquitectura.md (D01 a D28). Leelo completo antes de preguntar nada; no reabras decisiones tomadas salvo que encuentres una contradicción, y en ese caso señalala.

Alcance de este ciclo: F0 (esqueleto) y F1 (plantilla y calendario) según docs/plan-de-implementacion.md.

Lo que esperamos al final:
1. Proyecto FastAPI en backend/ conectado a Supabase con SQLAlchemy y Alembic.
2. Reloj inyectable para toda la lógica que dependa de la hora actual (D26).
3. Tablas Medico, Casillero, VersionCasillero y VersionTitular, con la restricción de exclusión de vigencias (D10).
4. Cálculo de turnos desde la plantilla con rotación por ciclo (D13, D14), incluidos turnos que cruzan medianoche.
5. GET /turnos?desde&hasta devolviendo turnos calculados con id "casilleroId:fecha" (D09).
6. Script de datos de ejemplo: unos 10 médicos, un coordinador, una rotación A/B y guardias que cruzan medianoche.
7. Pruebas con pytest contra Postgres que cubran rotación, medianoche y cambio de versión de plantilla.

Hacé las preguntas que necesites antes de escribir el spec.
```
