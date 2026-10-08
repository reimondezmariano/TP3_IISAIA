# Guion del Demo Day

Demo Day: 14/10/2026, por Google Meet. Duración: 6 minutos. Florencia comparte pantalla.

Este guion describe lo que la app hace hoy (main al 8/10/2026). Cada paso dice qué cuenta actúa, qué se toca en pantalla y qué se tiene que ver. Los turnos se nombran con su identificador de la API, "horarioId:fecha" (D09).

## Preparación

### Una sola vez, antes del primer ensayo

1. Supabase: **Confirm email** apagado y migraciones aplicadas (pasos 2 y 3 de `docs/despliegue.md`). Render publicado desde main con `MODO_DEMO` en `true` (viene así en `render.yaml`).
2. Datos de ejemplo en Supabase, con `DATABASE_URL` apuntando a Supabase (desde `backend/`):

   ```bash
   .venv/bin/python -m scripts.seed --confirmar
   ```

   Carga 10 médicos, el coordinador Enzo y 14 horarios pactados. Los emails son `nombre.apellido@guardiaviva.test`; el del coordinador, `enzo@guardiaviva.test`.
3. Cuentas: en la app publicada, cada una se crea con **Registrarme**, con el email del seed y una contraseña que elige quien la va a usar:
   1. `florencia.lucca@guardiaviva.test`, `mariano.reimondez@guardiaviva.test` y `carlos.lugones@guardiaviva.test`: sin código. El servidor reconoce el email del seed y las deja activas como médicos (D28).
   2. `enzo@guardiaviva.test`: con el código de coordinación (D30). Sin el código, el servidor rechaza vincular una cuenta de coordinador.

   El seed conserva estos vínculos: después de reiniciar la demo nadie tiene que volver a registrarse.
4. Perfiles de Chrome: uno por cuenta (Enzo, Florencia, Mariano), cada uno con su sesión iniciada. Carlos entra desde su celular; la app se puede instalar (PWA).

### Antes de cada ensayo y del Demo Day

1. Reiniciar la demo con el mismo comando del seed. Borra vacantes, postulaciones, notificaciones e historia, y vuelve el reloj de demo a la hora real.
2. Si el ensayo es antes del 14/10, la semana que se ve no es la del Demo Day. Después del seed, adelantar el reloj al 14/10 a la hora del ensayo (ver "Reloj de demo"). El reloj solo avanza: para volver, se reinicia la demo.
3. Diez minutos antes, abrir la app en Render. El plan gratis duerme el servicio después de unos 15 minutos sin uso, y el primer pedido tarda hasta un minuto en despertarlo. Dejarla abierta y recargar cada tanto hasta empezar.
4. En los perfiles de Mariano y de Carlos (y en el celular), borrar los datos del sitio (herramientas de desarrollador, **Application**, **Clear site data**) y volver a iniciar sesión. El navegador recuerda el id de cada postulación, y después del seed esos ids ya no valen: sin borrarlos, el sábado mostraría "Retirar postulación" en lugar de "Postularme".
5. Recargar las ventanas (F5) después del seed: el calendario no se actualiza solo.
6. La demo tiene que empezar antes de las 20:00 del 14/10. La vacante urgente del paso 6 usa la guardia de Florencia de ese día a las 20:00, y una vacante es urgente cuando se genera a menos de 24 h del inicio.

### Reloj de demo

No hay botón en la interfaz. Se mueve con `POST /api/demo/reloj`, que exige un coordinador, desde la consola de las herramientas de desarrollador de la ventana de Enzo. Dejar los comandos escritos de antemano y recuperarlos con la flecha hacia arriba:

```js
const reloj = async (ahora) => {
  const clave = Object.keys(localStorage).find((k) => k.endsWith("-auth-token"));
  const token = JSON.parse(localStorage[clave]).access_token;
  const r = await fetch("/api/demo/reloj", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ ahora }),
  });
  return r.json();
};
await reloj("2026-10-14T20:30:00-03:00");
```

Responde con la hora nueva y el desfase. Después de moverlo hay que recargar (F5) las ventanas que se van a usar: el calendario toma "ahora" del servidor al cargar (D27).

## Pantalla compartida

Tres ventanas de la app y Render en cuadrícula, cada ventana con su propio perfil de Chrome.

| | Izquierda | Derecha |
|---|---|---|
| Arriba | Enzo, coordinador, con la consola abierta para el reloj de demo | Florencia, médica, con las herramientas de desarrollador en la pestaña Network |
| Abajo | Mariano, médico | Render, pestaña Logs del servicio |

Carlos actúa desde su celular. Sus acciones se ven en las otras ventanas al recargar, y lo que le pasa a él le llega a su campanita: la app es multiusuario de verdad.

Ajustes de la pantalla:
1. Zoom de las ventanas al 80 o 90 %.
2. En Network, filtro `/vacantes|postulaciones|asignacion/`. Así no se ven las consultas de notificaciones, que se repiten cada 12 s.
3. Los logs de Render muestran una línea por pedido (método, ruta y código de respuesta). La app no escribe logs de dominio propios.

## Estructura

| Tiempo | Bloque | Quién | Qué demuestra |
|---|---|---|---|
| 0:00 a 0:40 | El problema | Carlos | Que el problema es real y lo conoce un usuario del servicio |
| 0:40 a 3:40 | Demo en vivo | Florencia maneja, Mariano narra, Carlos desde el celular | Que la aplicación funciona de punta a punta |
| 3:40 a 5:40 | Decisiones y proceso | Mariano y Florencia | Decisiones, gestión del contexto y qué salió mal |
| 5:40 a 6:00 | Cierre | Carlos | Trabajo futuro y valor para el servicio |

## Bloque 1: el problema (Carlos, 40 s)

Hoy las ausencias se avisan por WhatsApp y el coordinador actualiza una planilla Excel a mano. Cuando nadie cubre, los demás médicos trabajan el doble, y eso no queda registrado en ningún lado.

## Bloque 2: la demo (3 min)

Colores del semáforo (D08), con la leyenda arriba del calendario: verde cubierta, ámbar vacante abierta, naranja vacante urgente, rojo BAJA (sin titular, D24). Postularse no cambia el color.

1. **Calendario de la semana (15 s). Florencia.** Mostrar la semana del 12 al 18 de octubre: todo verde, horarios de 6, 8, 12 y 24 h, y la guardia de Florencia del miércoles a las 20:00 con "(+1 día)", porque cruza la medianoche. El día de hoy está resaltado. Mensaje: nadie carga guardias; salen de los horarios pactados.
2. **Florencia avisa su ausencia del sábado (30 s). Florencia.** Tocar la tarjeta del sábado 17, 08:00 a 20:00, escribir un motivo y tocar **Avisar ausencia**. Se tiene que ver:
   1. La tarjeta pasa a ámbar con la etiqueta "Vacante".
   2. En Network, el pedido `POST /api/turnos/1:2026-10-17/vacantes` con respuesta 201. Abrirlo para mostrar el identificador "horarioId:fecha" (D09).
   3. En Render, la línea del POST con 201.

   Mensaje: el turno no existía en la base; se guarda recién ahora, porque le pasó algo (D11). Una vacante que no es urgente no manda notificaciones: los demás la ven al recargar.
3. **Mariano y Carlos se postulan (25 s).** Mariano recarga, toca la tarjeta ámbar del sábado y toca **Postularme**. Carlos hace lo mismo desde el celular, después de Mariano. La tarjeta sigue ámbar.
4. **Enzo elige a Mariano (25 s). Enzo.** Recargar, tocar la tarjeta del sábado: en el detalle aparece el panel **Cobertura** con los candidatos. El orden es por equidad: primero quien cubrió menos guardias en el mes. Los dos tienen 0 coberturas, así que desempata quién se postuló antes (D17). Al lado de cada uno se ven las horas que ya tiene esa semana, como dato. Tocar **Elegir** en Mariano. Se tiene que ver:
   1. El mensaje "Mariano Reimondez cubre este turno." y la tarjeta en verde.
   2. A los pocos segundos (hasta 12 s), en la campanita de Mariano: "Te asignaron la guardia del 17/10 a las 08:00."
5. **Cancelación de último momento (35 s).**
   1. Mariano: en el detalle del sábado, **Retirar postulación**. Retirarla no le saca la guardia.
   2. Enzo: en el detalle del sábado (verde), escribir el motivo "Mariano no puede" y tocar **Generar vacante**. La tarjeta vuelve a ámbar y el turno queda sin asignado (D31).
   3. En el panel **Cobertura**, Carlos ya figura como candidato sin haber hecho nada: su postulación sigue en pie. Enzo toca **Elegir** en Carlos; la tarjeta vuelve a verde y a Carlos le llega el aviso al celular.

   Mensaje: la postulación es al turno, no a la vacante, y por eso la reserva sobrevive (D08).
6. **Lo que nadie cubre (50 s).**
   1. Florencia: tocar su guardia de hoy, miércoles 14 a las 20:00, y **Avisar ausencia**. Como empieza en menos de 24 h, la tarjeta pasa a naranja ("Vacante urgente"). En hasta 12 s aparece el aviso emergente "Vacante urgente: guardia del 14/10 a las 20:00." en la ventana de Mariano y en el celular de Carlos. A Florencia no le aparece, porque la generó ella.
   2. Enzo, en la consola: `await reloj("2026-10-14T20:30:00-03:00")` y recargar. Nadie se postuló y el turno ya empezó. En su campanita aparece "La guardia del 14/10 a las 20:00 sigue sin cobertura: ya empezó." (D19). Tocar la tarjeta y **Marcar sin cobertura**; se ve "El turno quedó marcado sin cobertura."
   3. Enzo, en la consola: `await reloj("2026-10-15T08:30:00-03:00")` y recargar. El turno terminó y se consolidó. El indicador de arriba del calendario pasa de "0 h sin cobertura en octubre de 2026" a "12 h sin cobertura en octubre de 2026 (1 turno)".

   Mensaje: hoy ese trabajo doble es invisible; ahora queda medido.

   Ojo: después de marcarlo sin cobertura, la tarjeta vuelve a verde, porque el turno ya no tiene una vacante abierta. No señalar la tarjeta en ese momento: mostrar la campanita y el indicador.

Si sobran 15 s: abrir `/docs` en Render y mostrar el contrato de la API generado automáticamente.

## Bloque 3: decisiones y proceso (2 min)

GitHub en vivo, con diapositivas de respaldo con el mismo contenido.

1. Arquitectura (20 s): interfaz web, FastAPI, Postgres en Supabase. "El futuro normal se calcula, el presente excepcional se guarda, el pasado se consolida". Momento opcional de 10 s en Supabase, en el Table Editor:
   1. Tabla `turno`: hay filas para los días ya pasados (consolidados) y, para adelante, solo para el sábado 17 y el miércoles 14, que tuvieron novedades.
   2. Tabla `evento_turno`: la bitácora de lo que acaba de pasar (VACANTE_GENERADA, POSTULACION_CREADA, CANDIDATO_ELEGIDO, POSTULACION_RETIRADA, TURNO_SIN_COBERTURA), con quién lo hizo. La interfaz todavía no muestra la línea de tiempo del turno.
2. Dos decisiones (50 s):
   1. Por qué C5 y no C1 o C4: turno guardado solo cuando le pasa algo, con una restricción única que resuelve la concurrencia y la consolidación.
   2. La validación con Carlos eliminó complejidad imaginada: rotaciones y ranking por descanso.
3. Proceso (30 s): cómo trabajamos con Superpowers (brainstorming, spec, plan, implementación por subagentes, revisión de código, pull request), con los specs y planes en docs/superpowers, la lista de pull requests con sus revisiones y el diseño documentado en CLAUDE.md.
4. Qué salió mal (20 s): la sesión que trabajó con decisiones desactualizadas.

## Bloque 4: cierre (Carlos, 20 s)

Trabajo futuro: notificaciones push, mail para vacantes urgentes, intercambios entre médicos. Valor: el indicador de horas sin cobertura da evidencia para pedir más médicos.

## Qué tiene que funcionar sí o sí

Login con roles, calendario con semáforo, avisar ausencia, postularse y retirar la postulación, candidatos por equidad y asignación, reserva después de una cancelación, notificaciones y aviso emergente, reloj de demo, turno sin cobertura con alerta al coordinador e indicador.

Está implementado pero no entra en el recorrido principal: pantalla de staff (pestaña **Staff**, solo para Enzo), baja de un médico con sus horarios marcados BAJA y designar un titular nuevo, registro con código de coordinación, avisar ausencia en varias fechas, asignación directa y reasignación desde el panel de cobertura. Si sobra tiempo, se muestra la pantalla de staff (15 s).

No está implementado: la línea de tiempo del turno en la interfaz (no existe `GET /api/turnos/{turnoId}`) y la rectificación (no existe `POST /api/turnos/{turnoId}/rectificacion`).

## Datos de ejemplo (lo que carga el seed)

1. Médicos Florencia Lucca, Mariano Reimondez y Carlos Lugones, más 7 ficticios; coordinador Enzo.
2. Florencia: sábado 08:00, 12 h (horario 1, turno `1:2026-10-17` para los pasos 2 a 5) y miércoles 20:00, 12 h, que cruza la medianoche (horario 2, turno `2:2026-10-14` para el paso 6).
3. Horarios de 6, 8, 12 y 24 h, dos semana por medio que se alternan y uno que cambió de hora el 28/9.
4. Historia: los horarios rigen desde el 7/9, así que al abrir el calendario las semanas pasadas se consolidan con el titular como realizador. No carga vacantes, postulaciones ni guardias sin cobertura: el indicador arranca en 0 h.
5. El mismo comando reinicia la demo (borra todo, vuelve el reloj a la hora real y conserva las cuentas).

## Plan de respaldo: todo desde una sola computadora

Si Carlos no se puede conectar o falla alguna computadora del equipo, Florencia hace toda la demo sola.

1. Preparar un cuarto perfil de Chrome con la sesión de Carlos y ensayarlo así al menos una vez. En la cuadrícula, la ventana de Carlos reemplaza a la de Render; los logs se muestran en otra pestaña si hace falta.
2. Mariano narra igual. Florencia hace los pasos de todos, en el mismo orden, y dice en voz alta qué cuenta está usando en cada uno.
3. Si Render no responde (sigue dormido después de un minuto o da error):
   1. Levantar la app en la computadora con la compilación del frontend servida por el backend, contra el Postgres local:

      ```bash
      docker compose up -d --wait
      cd frontend && npm run build
      cd ../backend && .venv/bin/alembic upgrade head && .venv/bin/python -m scripts.seed --confirmar
      MODO_DEMO=true .venv/bin/uvicorn app.main:app --port 8000
      ```

      `backend/.env` tiene que apuntar al Postgres local y tener el código de coordinación; `frontend/.env`, las variables públicas de Supabase. Las cuentas siguen en Supabase Auth, así que hace falta internet.
   2. Abrir `http://localhost:8000` en los cuatro perfiles. En la base local las cuentas todavía no están vinculadas: cada una entra con su email y contraseña y completa **Completá tu registro** (Enzo con el código de coordinación). Conviene hacerlo el día anterior, porque el seed conserva los vínculos.
   3. Los logs se ven en la terminal de uvicorn, en lugar de Render.
4. Si no hay forma de correr la app: el video del último ensayo completo y las diapositivas de respaldo con capturas reales.

## Pendiente

1. Consultar a Enzo si quiere operar él la cuenta de coordinador (solo requiere que cree su cuenta con `enzo@guardiaviva.test` y el código).
2. Ensayar el plan de respaldo desde una sola computadora, incluida la app local.
3. Grabar un ensayo completo como respaldo.
4. Diapositivas de respaldo del bloque 3, con capturas reales.
