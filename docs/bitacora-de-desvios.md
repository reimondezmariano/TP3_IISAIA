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
