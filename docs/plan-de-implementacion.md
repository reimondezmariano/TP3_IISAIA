# Guardia Viva: cómo pasamos a Claude Code

## Preparación (una sola vez)

1. Clonar el repo de Mariano. Mariano suma a Carlos y Florencia como colaboradores y le avisa a Enzo por mail cuál es el repo del TP.
2. Copiar a la raíz del repo `CLAUDE.md` y la carpeta `docs/` con `decisiones-arquitectura.md` y este archivo. Cada cambio entra por branch y pull request.
3. Crear el proyecto en Supabase (región São Paulo, la más cercana) y la cuenta de Gmail del coordinador de la demo.
4. Instalar los plugins y herramientas que mostró Enzo. Importante: trabajar con Claude Code en la propia computadora (terminal, extensión de VS Code o sesión local de la app de escritorio). Las sesiones en la nube, como claude.ai/code, no cargan plugins.
   1. Superpowers, según dónde usen Claude Code:
      1. Terminal: dentro de una sesión de `claude`, `/plugin install superpowers@claude-plugins-official`; o desde la shell, sin abrir sesión, `claude plugin install superpowers@claude-plugins-official --scope project`.
      2. VS Code (lo que usa Enzo): escribir `/plugins` solo, sin nada más, en el panel de Claude; se abre "Manage plugins"; buscar superpowers e instalar con alcance de proyecto.
      3. App de escritorio, sesión local: botón + junto al cuadro de texto, Plugins, Add plugin.
      4. Si no aparece en el marketplace oficial, agregar antes el que mostró Enzo: `/plugin marketplace add obra/superpowers-marketplace` (o `claude plugin marketplace add obra/superpowers-marketplace` desde la shell).
      5. Con alcance de proyecto queda habilitado en `.claude/settings.json` para los tres, pero cada uno tiene que correr la instalación una vez en su computadora.
   2. Playwright MCP, para que el agente pruebe la interfaz por su cuenta: desde la terminal, `claude mcp add playwright npx @playwright/mcp@latest`.
5. Abrir la sesión parados en la raíz del repo y verificar con `/context` que cargó el CLAUDE.md.

## Orden de funcionalidades

Cada funcionalidad es un ciclo completo de Superpowers: brainstorming, spec, plan, implementación por subagentes, revisión y pull request. Cada ciclo arranca en una sesión nueva.

| # | Funcionalidad | Contenido | Fecha objetivo |
|---|---|---|---|
| F0 | Esqueleto | Estructura de carpetas, FastAPI, conexión a Supabase, Alembic, pytest, reloj inyectable, CLAUDE.md de backend y frontend | 5/10 |
| F1 | Plantilla y calendario | Usuario con rol, HorarioPactado, VersionHorario, GET /turnos calculado, script de datos de ejemplo | 6/10 |
| F2 | Vacantes y postulaciones | Turno materializado, Vacante (incluida la urgente), Postulacion, semáforo calculado, reglas de elegibilidad, bitácora | 7/10 |
| F3 | Candidatos y asignación | Lista de candidatos con datos informativos, PUT asignacion con sus tres casos, pruebas de concurrencia | 8/10 |
| F4 | Historia y alertas | Consolidación perezosa, turno sin cobertura, indicador de horas sin cobertura, rectificación, alertas escalonadas, notificaciones, reloj de demo | 9/10 |
| F5 | Seguridad y usuarios | Supabase Auth, roles, RLS, baja con transferencia o cierre de horarios | 9/10 |
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
/brainstorming Vamos a construir el backend de Guardia Viva. El brainstorming de arquitectura ya está hecho y sus decisiones están en docs/decisiones-arquitectura.md (D01 a D29). Leelo completo antes de preguntar nada; no reabras decisiones tomadas salvo que encuentres una contradicción, y en ese caso señalala.

Alcance de este ciclo: F0 (esqueleto) y F1 (plantilla y calendario) según docs/plan-de-implementacion.md.

Lo que esperamos al final:
1. Proyecto FastAPI en backend/ conectado a Supabase con SQLAlchemy y Alembic.
2. Reloj inyectable para toda la lógica que dependa de la hora actual (D27).
3. Tablas Usuario (rol MEDICO o COORDINADOR, D23), HorarioPactado y VersionHorario, con la restricción de exclusión de vigencias (D10).
4. Cálculo de turnos desde la plantilla (D13, D14: sin rotaciones), incluidos turnos que cruzan medianoche y horarios de distintos médicos superpuestos.
5. GET /turnos?desde&hasta devolviendo turnos calculados con id "horarioId:fecha" (D09).
6. Script de datos de ejemplo: unos 10 médicos con horarios pactados de duraciones variadas (6, 8, 12 y 24 h), uno o dos coordinadores y guardias que cruzan medianoche.
7. Pruebas con pytest contra Postgres que cubran medianoche, superposición entre médicos y cambio de versión de un horario.

Hacé las preguntas que necesites antes de escribir el spec.
```
