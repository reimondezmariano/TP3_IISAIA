# Guion del Demo Day

Demo Day: 14/10/2026, por Google Meet. Duración: 6 minutos. Una persona comparte pantalla.

## Pantalla compartida

Cuatro paneles en cuadrícula. Cada ventana del navegador con su propio perfil de Chrome, para que cada una tenga su propia sesión.

| | Izquierda | Derecha |
|---|---|---|
| Arriba | Coordinador "Enzo" | Florencia, médica, con las herramientas de desarrollador abiertas en la pestaña Network |
| Abajo | Mariano, médico | Terminal con los logs del backend |

Carlos se postula desde su computadora o su celular: su acción aparece en vivo en la ventana del coordinador, lo que demuestra que la aplicación es multiusuario de verdad.

Preparación de la pantalla: zoom de las ventanas al 80 o 90%, letra grande en la terminal, filtro de Network con el texto `vacantes` o `postulaciones` para ocultar las consultas periódicas de notificaciones.

## Estructura

| Tiempo | Bloque | Quién | Qué demuestra |
|---|---|---|---|
| 0:00 a 0:40 | El problema | Carlos | Que el problema es real y lo conoce un usuario del servicio |
| 0:40 a 3:40 | Demo en vivo | Florencia maneja, Mariano narra | Que la aplicación funciona de punta a punta |
| 3:40 a 5:40 | Decisiones y proceso | Mariano y Florencia | Decisiones, gestión del contexto y qué salió mal |
| 5:40 a 6:00 | Cierre | Carlos | Trabajo futuro y valor para el servicio |

## Bloque 1: el problema (Carlos, 40 s)

Hoy las ausencias se avisan por WhatsApp y el coordinador actualiza una planilla Excel a mano. Cuando nadie cubre, los demás médicos trabajan el doble, y eso no queda registrado en ningún lado.

## Bloque 2: la demo (3 min)

1. Calendario de la semana (20 s). Todo en verde por defecto: horarios pactados de distintas duraciones y una guardia que cruza la medianoche. Mensaje: nadie carga guardias; salen de los horarios pactados.
2. Florencia genera una vacante para su guardia del sábado (30 s). El turno pasa a rojo y la notificación aparece en las otras ventanas. En Network se abre el pedido y se muestra la respuesta del servidor; en la terminal, el log indica que el turno se guardó en la base recién ahora.
3. Mariano y Carlos se postulan (30 s). El turno pasa a amarillo.
4. El coordinador elige a Mariano (30 s). Ve los candidatos ordenados por equidad (primero quien cubrió menos vacantes en el mes) y elige; el turno pasa a verde. Se abre la línea de tiempo del turno, con cada evento y quién lo hizo.
5. Cancelación de último momento (30 s). Mariano cancela, se reabre la vacante y Carlos ya figura como candidato en reserva. El coordinador lo elige en un clic. Mensaje: la postulación es al turno, no a la vacante, y por eso la reserva sobrevive.
6. Lo que nadie cubre (40 s). Se genera una vacante urgente: aparece el aviso emergente en las ventanas de los médicos. Con el reloj de demo se adelanta el tiempo: la vacante sin postulantes llega a su hora de inicio, el coordinador la marca sin cobertura y el indicador de horas sin cobertura del mes sube. Mensaje: hoy ese trabajo doble es invisible; ahora queda medido.

Si sobran 15 s: abrir /docs y mostrar el contrato de la API generado automáticamente.

## Bloque 3: decisiones y proceso (2 min)

GitHub en vivo, con diapositivas de respaldo con el mismo contenido.

1. Arquitectura (20 s): interfaz web, FastAPI, Postgres en Supabase. "El futuro normal se calcula, el presente excepcional se guarda, el pasado se consolida". Momento opcional de 10 s: la tabla Turno en Supabase, con filas solo para las guardias que tuvieron novedades.
2. Dos decisiones (50 s):
   1. Por qué C5 y no C1 o C4: turno guardado solo cuando le pasa algo, con una restricción única que resuelve la concurrencia y la consolidación.
   2. La validación con Carlos eliminó complejidad imaginada: rotaciones y ranking por descanso.
3. Proceso (30 s): cómo trabajamos con Superpowers (brainstorming, spec, plan, implementación por subagentes, revisión de código, pull request), con los specs y planes en docs/superpowers, la lista de pull requests con sus revisiones y el diseño documentado en CLAUDE.md.
4. Qué salió mal (20 s): la sesión que trabajó con decisiones desactualizadas.

## Bloque 4: cierre (Carlos, 20 s)

Trabajo futuro: notificaciones push, mail para vacantes urgentes, intercambios entre médicos. Valor: el indicador de horas sin cobertura da evidencia para pedir más médicos.

## Qué tiene que funcionar sí o sí

Calendario, vacantes, postulaciones, asignación, reserva, notificaciones, reloj de demo, turno sin cobertura con su indicador, línea de tiempo del turno, login con roles y logs de dominio.

Se implementa pero no se muestra en el recorrido principal: pantalla de staff, baja de un médico con sus horarios marcados BAJA, registro con código de coordinación, rectificación. Si sobra tiempo, se muestra la pantalla de staff y un horario marcado BAJA (15 s).

## Datos de ejemplo necesarios

1. Médicos Florencia, Mariano y Carlos, más unos 7 ficticios; coordinador "Enzo".
2. Una guardia de Florencia el sábado 17/10.
3. Una guardia que cruce la medianoche en la semana del Demo Day.
4. Dos semanas de historia consolidada, con al menos una guardia sin cobertura, para que el indicador no arranque en cero.
5. Un turno preparado para la vacante urgente del paso 6.
6. Un script que deja la base en este estado inicial; se corre antes de cada ensayo y antes del Demo Day.

## Pendiente

1. Consultar a Enzo si quiere operar como coordinador al final (extra; solo requiere agregar su email).
2. Ensayar el plan de respaldo: todo desde una sola computadora.
3. Diapositivas de respaldo del bloque 3, con capturas reales.
