# Guardia Viva

Aplicación para gestionar las guardias médicas de un servicio hospitalario de 10 a 12 médicos. Reemplaza un grupo de WhatsApp y una planilla Excel. TP final de la materia Introducción a la ingeniería de software asistida por IA (Maestría en IA). Demo Day: 14/10/2026.

Antes de cambiar el modelo de datos o las reglas de negocio, leé `docs/decisiones-arquitectura.md`. Cada decisión tiene un código (D01 a D28); citalo en specs, planes y commits cuando corresponda.

## Stack

1. Backend: Python, FastAPI, SQLAlchemy, Alembic.
2. Base: Supabase (Postgres). RLS activado sin políticas; el backend se conecta con credenciales propias.
3. Autenticación: Supabase Auth con Google. El backend verifica el token y busca al médico por email.
4. Frontend: web responsive instalable (PWA), servida como estáticos por el backend. Parte del prototipo existente en memoria.
5. Pruebas: pytest contra Postgres (nunca contra SQLite: el modelo usa índices parciales y restricciones de exclusión).

## Estructura

1. `backend/`: API, dominio, persistencia, migraciones, scripts (seed y reinicio de demo). Tiene su propio CLAUDE.md.
2. `frontend/`: interfaz. Tiene su propio CLAUDE.md.
3. `docs/decisiones-arquitectura.md`: decisiones del brainstorming.
4. `docs/superpowers/specs` y `docs/superpowers/plans`: specs y planes de cada funcionalidad.

## Reglas del dominio que nunca se rompen

1. El futuro normal se calcula desde la plantilla; un turno se guarda solo cuando se genera una vacante o cuando se consolida (D11).
2. Identidad del turno: casillero + fecha de inicio; en la API "casilleroId:fecha" (D09).
3. Un turno ya materializado no se recalcula si cambia la plantilla (D11, D12).
4. El semáforo se calcula; no existe una columna de semáforo (D08).
5. Toda acción de dominio es una transacción que incluye su evento en la bitácora y sus notificaciones (D22).
6. La bitácora solo se agrega; nunca se edita ni se borra.
7. Los permisos se validan en el backend, aunque la interfaz oculte la acción.
8. La concurrencia se resuelve con restricciones de la base, no con lógica en memoria.
9. Nunca se borra un médico (D24).
10. Toda hora se interpreta en America/Argentina/Buenos_Aires y se guarda con zona horaria. Toda lógica que dependa de "ahora" usa el reloj inyectable (D26), nunca la hora del sistema directamente.

## Forma de trabajo

1. Una branch por funcionalidad (feature/nombre-corto). Flujo de Superpowers para funcionalidades grandes; cambios chicos sin el flujo completo.
2. Commits chicos, en español, que describen el cambio.
3. Merge a main mediante pull request en GitHub.
4. Antes de dar algo por terminado: correr las pruebas y, si tocaste la interfaz, verificarla con Playwright.
5. Si una tarea contradice una decisión de `docs/decisiones-arquitectura.md`, frená y preguntá en lugar de improvisar.

## Comandos

(Completar cuando exista el esqueleto: levantar el backend, correr pruebas, migrar, cargar datos de ejemplo, reiniciar la demo.)
