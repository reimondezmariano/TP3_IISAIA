# Bitácora de desvíos

Registro de los momentos en que el agente se fue para otro lado o trabajó con información equivocada: qué pasó, cómo lo detectamos y cómo lo corregimos. Es la fuente de la sección "Qué salió mal" del README.

Formato de cada entrada: fecha, qué pasó, cómo lo detectamos, cómo lo corregimos, qué aprendimos.

## 2026-10-04. Sesión de Claude Code con decisiones desactualizadas

Qué pasó: el 3/10 abrimos una sesión de Claude Code con Superpowers para F0 y F1. La sesión leyó la versión de docs/decisiones-arquitectura.md anterior a la validación con Carlos y empezó a diseñar el modelo viejo (Casillero, VersionTitular, rotación por ciclo). Mientras tanto, el 4/10 Carlos respondió las preguntas de dominio y el modelo cambió: no hay rotaciones, el coordinador no hace guardias y no existe prioridad por descanso.

Cómo lo detectamos: al retomar la sesión, el resumen inicial del agente ("Qué entendí") seguía mencionando entidades que ya habíamos eliminado.

Cómo lo corregimos: no respondimos en esa sesión y la cerramos antes de que escribiera el spec. Guardamos la versión anterior de las decisiones en la branch backup/decisiones-v1, subimos los documentos corregidos mediante el PR #2 y abrimos una sesión nueva. Le pasamos al agente las respuestas a las preguntas técnicas que ya había hecho, para no repetir la ronda.

Qué aprendimos: el contexto de una sesión es una foto del momento en que se abrió. Si cambian las decisiones, se abre una sesión nueva en lugar de corregir la vieja. El resumen "Qué entendí" del inicio es el punto de control para detectar contexto desactualizado.

## 2026-10-05. Defectos del plan corregidos durante la implementación de F0 y F1

Qué pasó: el plan escrito por el agente tenía código que no funcionaba tal cual en cuatro puntos. El formato de log de alembic.ini con `%%` imprimía el texto literal. Una prueba esperaba IntegrityError para un rango de vigencia invertido, pero Postgres rechaza antes el daterange generado con DataError. Pytest no encontraba el paquete `scripts` (se agregó `pythonpath`). La versión de Starlette instalada depreca `httpx` en el TestClient (se silenció el aviso con un filtro). Además, la revisión de la tarea del modelo encontró que las pruebas de restricciones no verificaban qué restricción rechazaba la fila y que una prueba dependía del orden de ejecución.

Cómo lo detectamos: los subagentes implementadores lo reportaron como desvíos al correr las pruebas (TDD), y el revisor de cada tarea los evaluó.

Cómo lo corregimos: con correcciones mínimas aceptadas por el revisor. Las pruebas del modelo se reescribieron para verificar el nombre de la restricción, en una ronda de corrección con nueva revisión.

Qué aprendimos: el código del plan es una hipótesis hasta que corre. Pedirle al implementador que no debilite las pruebas y que reporte cada desvío deja la traza para la revisión.

## 2026-10-07. La revisión de F2 encontró una apropiación de cuentas aprobada en el plan

Qué pasó: la decisión 4 del plan de F2 (aprobada por el equipo) vinculaba por email cualquier Usuario cargado por el seed, sin pedir el código de coordinación, para que Enzo pudiera registrarse. Combinada con D06 (confirmación de email desactivada) y con emails de ejemplo que están en el repositorio, cualquiera con la URL desplegada podía crear en Supabase la cuenta enzo@guardiaviva.test y quedar como coordinador activo, salteando D30. La misma revisión encontró que la vinculación pisaba sin aviso una vinculación hecha en paralelo (regla 8). La implementación seguía el plan al pie de la letra: el error estaba en el plan, no en el código.

Cómo lo detectamos: la revisión de código de toda la branch, hecha por un subagente con contexto nuevo después de las seis tareas, cruzó la decisión 4 con D06 y con los emails del seed.

Cómo lo corregimos: el equipo eligió exigir el código para vincular un coordinador cargado (422 CODIGO_REQUERIDO) y aceptar el riesgo para los médicos cargados; quedó en D28 y en la decisión 4 del plan. La vinculación pasó a un UPDATE condicionado a auth_id vacío que responde 409 si otra cuenta ganó. Cada corrección empezó con una prueba que fallaba.

Qué aprendimos: aprobar decisiones una por una no alcanza; hay que mirarlas combinadas con las anteriores (acá, la 4 con D06). La revisión final con contexto nuevo es la que ve esos cruces.

## 2026-10-07. Menores de la revisión de F2 que quedan pendientes

Qué pasó: la revisión de código de F2 marcó siete puntos menores. Antes del pull request se corrigieron tres, cada uno en su commit: el umbral de la alerta limitado a 48H, 24H e INICIO; TOKEN_SIN_EMAIL con 403; y la aclaración sobre turno.creado_en en backend/CLAUDE.md. Los otros cuatro quedan pendientes:

1. Si el endpoint de claves públicas de Supabase (JWKS) responde algo que no es JSON (por ejemplo, la página de error de un proxy), PyJWT lanza un ValueError que no captura, y el backend responde 500 sin el formato de error. Si el JWKS llega sin claves, responde 401 TOKEN_INVALIDO aunque el problema sea de Supabase. Corrección propuesta: capturar ValueError alrededor de la búsqueda de la clave y responder 503 AUTH_NO_DISPONIBLE.
2. pyproject.toml pide `pyjwt[crypto]>=2.9`, pero la espera mínima antes de volver a pedir claves por un `kid` desconocido existe solo en versiones recientes. Subir el mínimo a la versión probada (2.15).
3. Al vincular un médico cargado, un código de coordinación correcto se ignora (decisión 4 del plan) y la respuesta no lo avisa. La interfaz de F6 tiene que explicarlo o la respuesta tiene que sumar un campo.
4. POST /api/registro no limita los intentos, y la respuesta 422 CODIGO_INVALIDO deja probar códigos sin límite. D30 ya reconoce que el código es un control simple; como mínimo, recomendar en .env.example un código largo y difícil de adivinar.

Cómo lo detectamos: revisión de código de toda la branch feature/f2-cimientos.

Cómo lo corregimos: todavía no; se anotan para F5 (seguridad y staff) o F6 (interfaz), según corresponda.

Qué aprendimos: separar en la revisión lo que bloquea el merge de lo que se puede anotar deja el pull request chico sin perder los hallazgos.

