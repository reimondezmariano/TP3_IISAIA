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
| F0 | Esqueleto | Estructura de carpetas, FastAPI, conexión a Supabase, Alembic, pytest, reloj inyectable, esqueleto de frontend con React y Vite, CLAUDE.md de backend y frontend | 5/10 |
| F1 | Plantilla y calendario | Usuario con rol, HorarioPactado, VersionHorario, GET /turnos calculado, script de datos de ejemplo | 6/10 |
| F2 | Cimientos | Supabase Auth (D06, D07), POST /registro con código de coordinación (D30), GET /me, permisos por estado y rol; tablas Turno, Vacante, Postulacion, EventoTurno y Notificacion en una sola migración | 7/10 |
| F2b | Vacantes y postulaciones | Reglas de vacantes (incluida la urgente) y postulaciones, semáforo calculado, elegibilidad, bitácora, logs de dominio legibles en la terminal (una línea por acción). Otro integrante, sobre las tablas de F2 | 8/10 |
| F3 | Candidatos y asignación | Lista de candidatos ordenada por equidad (D17), PUT asignacion con sus tres casos, pruebas de concurrencia | 8/10 |
| F4 | Historia y alertas | Consolidación perezosa, turno sin cobertura, indicador de horas sin cobertura, rectificación, alertas escalonadas, notificaciones (con aviso emergente para vacantes urgentes), reloj de demo | 9/10 |
| F5 | Seguridad y staff | Estados de usuario, API de staff, baja con horarios sin titular (D24) | 9/10 |
| F6 | Interfaz y despliegue | Frontend en React con Vite (frontend/), tomando el prototipo HTML como referencia visual: calendario, vacantes y candidatos, registro y login, pantalla de staff, aviso emergente, PWA; despliegue con el backend sirviendo la compilación | 10 y 11/10 |
| Cierre | Ensayo | Pruebas en celulares, README final, ensayo de la demo con el script de reinicio | 12 y 13/10 |

## Requisitos de entrega (lista de control)

| Requisito | Dónde se cumple | Estado |
|---|---|---|
| Frontend con framework visible en el repo, y el README indica dónde está | F6: React con Vite en frontend/, con package.json | Pendiente |
| Backend con persistencia | F0 a F5 | Pendiente |
| CLAUDE.md con el diseño documentado (modelo de datos, endpoints, contrato) | CLAUDE.md, sección Diseño | Hecho; actualizar si cambia el diseño |
| TP1 (Bad UI) incluido en el repo del TP final | Carpeta tp1-bad-ui/ con el TP1 individual de cada integrante | Pendiente |
| Idea presentada en la clase 5 | Ya presentada | Hecho |
| Al menos una funcionalidad hecha con Superpowers, con spec y plan en docs/superpowers/ | F0 + F1 en adelante | Pendiente |
| Commits seguidos a lo largo del trabajo, no uno solo de entrega | Todo el proceso | En curso |
| Branches feature/..., revisión de código y pull requests mergeados | Cada funcionalidad | En curso |
| README con: qué nos propusimos construir, prompts principales, cómo se ejecuta, arquitectura, qué decidimos, cómo gestionamos el contexto, qué salió mal | Cierre | Pendiente |
| Poder explicar Superpowers en la presentación | Guion, bloque 3 | Pendiente |
| Repo único con los tres como colaboradores y aviso al docente | Mariano | Pendiente |
| Presentación en la última clase | 14/10 | Pendiente |

## Consumo de tokens

1. Las sesiones de implementación las lleva quien tenga plan pago.
2. Pedir que los subagentes que implementan usen Sonnet o Haiku y que las revisiones usen Sonnet.
3. Para ajustes chicos (un texto, un color, un campo), no usar el flujo completo.

## Evidencia para el README (anotar sobre la marcha)

1. "Cómo gestioné el contexto": CLAUDE.md por nivel, documento de decisiones, una sesión por funcionalidad, subagentes, specs y planes en disco.
2. "Qué salió mal": cada vez que el agente se desvíe o una revisión encuentre un error, anotar en `docs/bitacora-de-desvios.md` qué pasó, cómo se detectó y cómo se corrigió. Al final se resume.
3. "Prompts principales": copiar en `docs/prompts-principales.md` el prompt con que arranca cada funcionalidad y cualquier prompt de corrección importante, con fecha y resultado.

## Primer prompt (F0 + F1)

Pegar en una sesión nueva de Claude Code, parados en la raíz del repo:

```
/brainstorming Vamos a construir el backend de Guardia Viva. El brainstorming de arquitectura ya está hecho y sus decisiones están en docs/decisiones-arquitectura.md (D01 a D30). Leelo completo antes de preguntar nada; no reabras decisiones tomadas salvo que encuentres una contradicción, y en ese caso señalala.

Alcance de este ciclo: F0 (esqueleto) y F1 (plantilla y calendario) según docs/plan-de-implementacion.md.

Lo que esperamos al final:
1. Proyecto FastAPI en backend/ conectado a Supabase con SQLAlchemy y Alembic, con un endpoint GET /health.
2. Esqueleto de frontend en frontend/ con React y Vite (package.json), con una página mínima que consulta GET /health. Las pantallas reales se hacen en F6.
3. Reloj inyectable para toda la lógica que dependa de la hora actual (D27).
4. Tablas Usuario (rol MEDICO o COORDINADOR y estado PENDIENTE, ACTIVO o BAJA, D23), HorarioPactado y VersionHorario (con médico opcional, para los horarios sin titular de D24), con la restricción de exclusión de vigencias (D10).
5. Cálculo de turnos desde la plantilla (D13, D14: frecuencia en semanas con fecha ancla), incluidos horarios semana por medio, turnos que cruzan medianoche y horarios de distintos médicos superpuestos.
6. GET /turnos?desde&hasta devolviendo turnos calculados con id "horarioId:fecha" (D09).
7. Script de datos de ejemplo que cubra lo que pide docs/guion-demo.md (sección "Datos de ejemplo necesarios"): unos 10 médicos con horarios pactados de duraciones variadas (6, 8, 12 y 24 h), entre ellos Florencia, Mariano y Carlos; un coordinador "Enzo"; guardias que cruzan medianoche; al menos un horario semana por medio. El script deja la base en ese estado cada vez que se corre. En este ciclo solo carga usuarios y horarios; la historia y las vacantes se suman en F2 a F4.
8. Pruebas con pytest contra Postgres que cubran medianoche, semana por medio, superposición entre médicos y cambio de versión de un horario.

Respuestas a preguntas técnicas que ya surgieron en una sesión anterior:
1. Pruebas contra Postgres local en Docker con docker-compose (Postgres 15). Supabase queda para desarrollo y demo.
2. El día de la semana es parte de VersionHorario: una renegociación puede cambiar el día.
3. Vigencias semiabiertas [vigenteDesde, vigenteHasta): vigenteHasta es el primer día en que la versión ya no rige; vacío significa vigente. Coincide con el daterange de Postgres.
4. GET /turnos devuelve los turnos cuyo intervalo se superpone con el rango pedido, desde las 00:00 de "desde" hasta las 24:00 de "hasta". Así una guardia que empieza a las 22:00 del lunes aparece también en el martes.
5. La conexión a Supabase usa el Session pooler; la cadena va en un archivo .env excluido del repo, que completamos nosotros.

Hacé las preguntas que necesites antes de escribir el spec.
```
