# F3: vacantes, postulaciones, candidatos y asignación. Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Objetivo:** exponer la API de operación del calendario: generar y retirar vacantes (incluido el lote), postularse, ver los candidatos ordenados por equidad y asignar, con las reglas de D15 a D22 y D31.

**Arquitectura:** tres etapas, cada una con su rama y su pull request, para que Carlos conecte las pantallas pronto y Florencia tenga cuanto antes la función de generar vacante. Etapa 1 publica el contrato con respuestas de ejemplo (rutas reales, datos fijos). Etapa 2 implementa generar vacante, lote y retiro. Etapa 3 implementa postulaciones, candidatos y asignación. Se sigue la estructura de `backend/CLAUDE.md`: reglas puras en `app/dominio/` (las de la primera etapa de F3 ya están en `main`), consultas en `app/repos/`, operaciones en `app/servicios/` (no hacen commit) y routers en `app/api/` (hacen el commit).

**Tecnologías:** Python 3.12, FastAPI, SQLAlchemy 2, pytest contra Postgres 15 local (puerto 5433). Sin dependencias nuevas.

**Spec:** no hay spec propio; las reglas están en `docs/decisiones-arquitectura.md` (D08 a D25, D31) y en el CLAUDE.md de la raíz (endpoints y contrato). Los supuestos de abajo completan lo que esas decisiones dejan abierto.

## Restricciones globales

- Rutas bajo `/api`; JSON en camelCase con `Esquema` (`app/api/esquemas.py`); instantes ISO 8601 con desplazamiento.
- Errores: `ErrorDominio(codigo, mensaje, status)`; 401 sin sesión, 403 rol insuficiente, 404 inexistente, 409 conflicto de estado o concurrencia, 422 regla de negocio. Ya existen `SIN_PERMISO` (403) y `TURNO_ID_INVALIDO` (422).
- Todo endpoint exige `usuario_actual`; los de coordinación, `requiere_coordinador`. El permiso fino (titular, asignado, dueño de la postulación) se valida en el servicio.
- Identificador de turno `"horarioId:fecha"` (D09). Un turno se guarda (materializa) solo cuando se genera una vacante o se postula a un turno sin titular; hasta entonces se calcula (D11).
- Nada fuera de `app/reloj.py` consulta la hora del sistema (D27): los instantes de dominio se completan con `reloj.ahora()` y las reglas puras reciben `ahora`.
- Toda acción de dominio escribe su `EventoTurno` (y sus notificaciones) en la misma transacción que el cambio (D22). La bitácora solo se agrega.
- Concurrencia con restricciones y bloqueos de la base, no en memoria (regla 8). Orden de bloqueos: filas de `usuario`, después `horario_pactado`, después `turno` (se agrega este último eslabón), y varias filas del mismo tipo siempre por id ascendente.
- El motivo de la vacante solo lo ven los coordinadores (D25): los demás reciben `motivo: null`.
- Los servicios no hacen commit; lo hace el router. Cada módulo de dominio nuevo es puro (sin base ni FastAPI).
- Pruebas con las fixtures `sesion`, `cliente`, `reloj` y `como_coordinador`; las de concurrencia, `@pytest.mark.commit_real`. El reloj de prueba es el lunes 12/10/2026 09:00; el horario de prueba por defecto es martes 08:00 a 20:00, así que su turno de ejemplo es `"<horarioId>:2026-10-13"`.
- Pruebas siempre contra Postgres; correr con `python -m pytest` desde `backend/` con el venv y `docker compose up -d --wait` levantado.
- Commits chicos, en español, con la decisión citada. Cada commit termina con la línea `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Un commit por tarea.

## Supuestos a confirmar con el equipo antes de ejecutar

Las decisiones de arriba no cierran estos puntos; el plan elige lo que sigue y, si el equipo aprueba, se documentan como D32 en adelante en la tarea 14.

1. **Cuándo se puede generar una vacante:** hasta el inicio del turno. Después (turno empezado o terminado) responde 409 `TURNO_YA_EMPEZO`; las coberturas parciales están fuera de alcance (D29).
2. **Quién genera:** el titular, el asignado vigente o un coordinador. Un turno sin titular (BAJA) y sin asignado solo lo puede abrir un coordinador.
3. **Quién retira una vacante:** quien la generó o un coordinador, solo mientras está ABIERTA (D15). Si al generarla se borró un asignado que era quien la generó, el retiro lo restaura (la vacante guarda su id en el evento `VACANTE_GENERADA`); si no, el turno vuelve a su titular.
4. **Cuándo se puede postular:** a un turno con vacante ABIERTA o sin titular (BAJA), hasta su inicio. La postulación sobrevive a la asignación (reserva, D16).
5. **Quién se postula y quién puede ser asignado:** un usuario con rol MEDICO y estado ACTIVO, o BAJA solo para turnos con fecha de inicio hasta su `fecha_baja` inclusive (decisión 16 del plan de F5). Nunca coordinadores ni PENDIENTES.
6. **Elegibilidad (D16):** los candidatos no elegibles se listan después de los elegibles, con su motivo, y no se pueden asignar (409 `CANDIDATO_NO_ELEGIBLE`). La asignación directa aplica las mismas reglas. "El coordinador puede elegir a cualquier candidato" se lee como "no está obligado a elegir al primero".
7. **Asignación (D18):** hasta el fin del turno. Si el turno ya tiene asignado, hay que enviar `reasignar: true` o responde 409 `YA_TIENE_ASIGNADO`; esto protege de dos coordinadores asignando a la vez. Asignar cierra la vacante ABIERTA como CUBIERTA. Asignar a quien ya está asignado responde 409 `YA_ASIGNADO`.
8. **Lote (D15):** todo o nada, hasta 31 turnos; ante un fallo responde el código del error con el `turnoId` que falló. Se bloquean los turnos por id ascendente.
9. **Notificaciones:** una vacante urgente crea una notificación `VACANTE_URGENTE` para cada médico ACTIVO salvo quien la generó (D05). Las demás notificaciones y `GET /notificaciones` son de F4.
10. **Quién ve los candidatos:** solo coordinadores. Los médicos ven si ellos mismos están postulados en los datos del turno (fuera de este plan).
11. **Re-postulación:** quien retiró su postulación y vuelve a postularse reactiva la misma fila con `creada_en` nueva (queda al final del desempate, D17).

## Fuera de este plan

`GET /turnos/{id}` (detalle y línea de tiempo), el estado o semáforo dentro de `GET /turnos` (hoy devuelve solo turnos calculados; el equipo tiene que definir los estados y colores antes), `POST /turnos/{id}/sin-cobertura`, rectificación, consolidación, alertas, indicador, notificaciones y reloj de demo (F4). La tarea 11 de F5 (reabrir coberturas al dar de baja) usa `generar_vacante` de la etapa 2.

## Foco de revisión

1. **Dos pedidos simultáneos sobre el mismo turno:** dos vacantes (una sola gana, la otra 409 `VACANTE_YA_ABIERTA`), dos asignaciones y una postulación contra una asignación. Pruebas `commit_real` en las tareas 6 y 13.
2. **Turno que no existe en la plantilla** (fecha en que el horario no se cumple, horario cerrado, id inventado): 404, y no se materializa nada. Prueba en la tarea 5.
3. **Turno materializado cuya plantilla cambió después:** la vacante y la elegibilidad usan la foto guardada (D11, D12), no la plantilla actual. Prueba en las tareas 5 y 10.
4. **Fuga del motivo (D25):** ni la respuesta de generar, ni la de retiro, ni el lote muestran el motivo a un médico. Prueba en la tarea 8.
5. **Médico dado de baja con fecha futura:** puede postularse a turnos hasta su `fecha_baja` inclusive y no después. Prueba en las tareas 9 y 11.

---

## Estructura de archivos

```
Etapa 1 (rama feature/f3-contrato-api)
  backend/app/api/esquemas_operacion.py          (T1)  schemas + EJEMPLOS
  backend/app/api/operacion.py                   (T2)  rutas con respuestas de ejemplo
  backend/tests/test_api_operacion_ejemplos.py   (T1, T2)
Etapa 2 (rama feature/f3-generar-vacante)
  backend/app/dominio/vacantes.py                (T4)  + puede_generar, puede_retirar
  backend/app/repos/turnos.py                    (T5)  materializar_turno, bloquear_turnos
  backend/app/servicios/vacantes.py              (T6, T7)  generar_vacante, generar_lote, retirar_vacante
  backend/app/api/vacantes.py                    (T8)  rutas reales
Etapa 3 (rama feature/f3-postulaciones-asignacion)
  backend/app/dominio/asignacion.py              (T9)  habilitado_para_turno, clasificar_asignacion
  backend/app/repos/guardias.py                  (T10) guardias_del_medico, turnos_del_mes
  backend/app/servicios/postulaciones.py         (T11, T12)  postular, retirar_postulacion, listar_candidatos
  backend/app/servicios/asignacion.py            (T13) asignar
  backend/app/api/postulaciones.py, asignacion.py (T14) rutas reales; se elimina api/operacion.py
```

---

# Etapa 1: contrato con respuestas de ejemplo (PR 1)

### Task 1: Esquemas del contrato y ejemplos

**Files:**
- Create: `backend/app/api/esquemas_operacion.py`
- Test: `backend/tests/test_api_operacion_ejemplos.py`

**Interfaces:**
- Produces (todos `Esquema`): `PersonaOut(id, nombre)`; `VacanteOut(id, turno_id: str, estado: EstadoVacante, urgente: bool, motivo: str | None, generada_por: PersonaOut, creada_en, cerrada_en: datetime | None)`; `GenerarVacanteIn(motivo: str | None = None)`; `LoteVacantesIn(turno_ids: list[str] (1 a 31), motivo: str | None = None)`; `LoteVacantesOut(vacantes: list[VacanteOut])`; `PostulacionOut(id, turno_id, medico: PersonaOut, creada_en, retirada_en: datetime | None)`; `CandidatoOut(posicion: int | None, medico: PersonaOut, postulado_en, coberturas_mes: int, horas_semana: float, elegible: bool, motivo_inelegibilidad: Motivo | None)`; `CandidatosOut(turno_id, mes: str "AAAA-MM", candidatos: list[CandidatoOut])`; `AsignarIn(medico_id: int, reasignar: bool = False)`; `CasoAsignacion(str, Enum)` = `CANDIDATO_ELEGIDO | ASIGNACION_DIRECTA | REASIGNACION`; `AsignacionOut(turno_id, asignado: PersonaOut, caso: CasoAsignacion, vacante: VacanteOut | None)`.
- Produces: `EJEMPLOS: dict[str, object]` con una instancia válida de cada `*Out` (clave = nombre de la clase), usando el turno `"7:2026-10-17"`; `posicion` es `null` para los no elegibles.

- [ ] **Step 1: Escribir las pruebas que fallan**: `test_cada_ejemplo_valida_contra_su_esquema` (parametrizada: `Clase.model_validate(EJEMPLOS[nombre].model_dump(by_alias=True))`), `test_los_ejemplos_salen_en_camel_case` (`"turnoId"` en el JSON de `VacanteOut`), `test_lote_rechaza_lista_vacia_y_mas_de_31` (`pytest.raises(ValidationError)`), `test_instantes_de_ejemplo_llevan_desplazamiento` (`"-03:00"` en el JSON de `VacanteOut`).
- [ ] **Step 2: Correr y verificar que fallan:** `python -m pytest tests/test_api_operacion_ejemplos.py -v` → FAIL (`ModuleNotFoundError`).
- [ ] **Step 3: Implementar** los esquemas y `EJEMPLOS`; que la documentación OpenAPI use esos ejemplos (`json_schema_extra={"examples": [...]}` o el equivalente de la versión instalada).
- [ ] **Step 4: Correr y verificar que pasan:** mismo comando → PASS.
- [ ] **Step 5: Commit** `git commit -m "Esquemas del contrato de vacantes, postulaciones y asignación, con ejemplos (D15 a D18)"`.

### Task 2: Rutas con respuestas de ejemplo

**Files:**
- Create: `backend/app/api/operacion.py`
- Modify: `backend/app/main.py` (incluir el router)
- Test: `backend/tests/test_api_operacion_ejemplos.py`

**Interfaces:**
- Consumes: esquemas y `EJEMPLOS` (T1); `usuario_actual`, `requiere_coordinador`.
- Produces: las 8 rutas del contrato, cada una con su `response_model`, que responden el ejemplo fijo, no persisten nada y agregan el encabezado `X-Respuesta-Ejemplo: true`:
  `POST /turnos/{turno_id}/vacantes` (201), `POST /vacantes/lote` (201, coordinador), `POST /vacantes/{vacante_id}/retiro` (200), `POST /turnos/{turno_id}/postulaciones` (201), `POST /postulaciones/{postulacion_id}/retiro` (200), `GET /turnos/{turno_id}/candidatos` (200, coordinador), `PUT /turnos/{turno_id}/asignacion` (200, coordinador). Una prueba del contrato verifica que las siete existen en el OpenAPI.

- [ ] **Step 1: Escribir las pruebas que fallan** (con `como_coordinador` y un médico): `test_las_siete_rutas_estan_en_el_openapi`, `test_sin_token_responde_401` (parametrizada por ruta), `test_medico_no_puede_usar_rutas_de_coordinacion` (lote, candidatos y asignación → 403 `SIN_PERMISO`), `test_la_respuesta_de_ejemplo_valida_y_lleva_el_encabezado` (parametrizada: el JSON valida contra el esquema y `X-Respuesta-Ejemplo == "true"`), `test_turno_id_mal_formado_responde_422` (`TURNO_ID_INVALIDO`, con `parsear_id_turno`), `test_la_ruta_de_ejemplo_no_escribe_en_la_base` (cuenta filas de `vacante`, `postulacion` y `evento_turno` antes y después).
- [ ] **Step 2: Correr y verificar que fallan** → FAIL (404 en las rutas).
- [ ] **Step 3: Implementar** el router y registrarlo en `crear_app`; `Response.headers` para el encabezado.
- [ ] **Step 4: Correr y verificar que pasan,** junto con la suite completa: `python -m pytest -q` → todo PASS.
- [ ] **Step 5: Commit** `git commit -m "Rutas de vacantes, postulaciones y asignación con respuestas de ejemplo para conectar la interfaz"`.

### Task 3: Documentar el contrato y abrir el PR 1

**Files:**
- Modify: `CLAUDE.md` (sección Endpoints: los cuerpos y el encabezado `X-Respuesta-Ejemplo`), `backend/CLAUDE.md` (módulos nuevos y la convención del encabezado), `docs/prompts-principales.md` (entrada de esta funcionalidad).

- [ ] **Step 1: Documentar** los cuerpos de pedido y respuesta de las siete rutas y el significado del encabezado (mientras exista, el dato es de ejemplo).
- [ ] **Step 2: Correr la suite completa** → PASS.
- [ ] **Step 3: Commit** `git commit -m "Documentar el contrato de operación y registrar el prompt"`; pushear y abrir el PR contra `main`; pedir revisión a Florencia y a Carlos; avisar a Carlos con el enlace.

---

# Etapa 2: generar vacante, lote y retiro (PR 2)

Rama nueva desde `main` actualizado: `feature/f3-generar-vacante`.

### Task 4: Reglas puras de permiso de vacantes

**Files:**
- Modify: `backend/app/dominio/vacantes.py`
- Test: `backend/tests/test_vacantes.py`

**Interfaces:**
- Produces: `puede_generar(actor_id: int, es_coordinador: bool, titular_id: int | None, asignado_id: int | None) -> bool` (supuesto 2); `puede_retirar(actor_id: int, es_coordinador: bool, generada_por_id: int) -> bool` (supuesto 3); `asignado_a_restaurar(generada_por_id: int, asignado_anterior_id: int | None) -> int | None`: devuelve `asignado_anterior_id` solo si coincide con `generada_por_id`.

- [ ] **Step 1: Escribir las pruebas que fallan:** el titular puede; el asignado puede; un tercero médico no puede; un coordinador siempre puede; con `titular_id=None` y `asignado_id=None` solo el coordinador; retira quien generó y el coordinador, no un tercero; `asignado_a_restaurar(5, 5) == 5`, `(5, 6) is None`, `(5, None) is None`.
- [ ] **Step 2: Correr y verificar que fallan:** `python -m pytest tests/test_vacantes.py -v` → FAIL.
- [ ] **Step 3: Implementar** las tres funciones.
- [ ] **Step 4: Correr y verificar que pasan** → PASS.
- [ ] **Step 5: Commit** `git commit -m "Reglas de permiso para generar y retirar vacantes (D15)"`.

### Task 5: Materializar y bloquear turnos

**Files:**
- Create: `backend/app/repos/turnos.py`
- Test: `backend/tests/test_repo_turnos.py`

**Interfaces:**
- Consumes: `versiones_en_rango`, `calcular_turnos`, `parsear_id_turno`, `ErrorDominio`.
- Produces: `materializar_turno(sesion: Session, turno_id: str, zona: ZoneInfo) -> Turno`: devuelve el turno ya guardado o lo calcula desde la plantilla (con la versión que rige ese día y la foto de D11), lo inserta con `INSERT ... ON CONFLICT DO NOTHING` y lo devuelve bloqueado (`FOR UPDATE`). Lanza 404 `TURNO_NO_ENCONTRADO` si la plantilla no lo produce. `bloquear_turnos(sesion, ids: Iterable[str], zona) -> list[Turno]`: materializa y bloquea por id compuesto en orden ascendente de `(horario_id, fecha)`.

- [ ] **Step 1: Escribir las pruebas que fallan** (con `crear_horario_de_prueba`): `test_materializa_con_la_foto_de_la_version` (inicio, fin, titular, versión), `test_es_idempotente` (dos llamadas, una sola fila), `test_turno_que_el_horario_no_produce_responde_404_y_no_guarda` (miércoles de un horario de martes), `test_horario_inexistente_responde_404`, `test_usa_la_foto_guardada_si_la_plantilla_cambio` (materializar, cambiar el titular de la plantilla, volver a pedir: sigue el titular viejo), `test_dos_materializaciones_simultaneas_dejan_una_fila` (`commit_real`, dos hilos), `test_bloquear_turnos_ordena_por_horario_y_fecha`.
- [ ] **Step 2: Correr y verificar que fallan:** `python -m pytest tests/test_repo_turnos.py -v` → FAIL.
- [ ] **Step 3: Implementar** ambas funciones; un solo turno calculado se obtiene pidiendo el rango `[fecha, fecha]` y filtrando por `horario_id`.
- [ ] **Step 4: Correr y verificar que pasan** → PASS.
- [ ] **Step 5: Commit** `git commit -m "Materializar y bloquear turnos desde la plantilla (D09, D11)"`.

### Task 6: Generar vacante

**Files:**
- Create: `backend/app/servicios/vacantes.py`
- Test: `backend/tests/test_servicio_vacantes.py`

**Interfaces:**
- Consumes: `materializar_turno` (T5), `puede_generar` (T4), `es_urgente`, `Reloj`.
- Produces: `@dataclass(frozen=True) ResultadoVacante(vacante: Vacante, turno: Turno, asignado_anterior_id: int | None)` y `generar_vacante(sesion: Session, turno_id: str, actor: Usuario, motivo: str | None, reloj: Reloj, zona: ZoneInfo) -> ResultadoVacante`. **Es la función que necesita F5 para la tarea 11.** Pasos en una transacción: materializa y bloquea el turno; 409 `TURNO_YA_EMPEZO` si `reloj.ahora() >= inicio`; 403 `SIN_PERMISO` si `not puede_generar(...)`; 409 `VACANTE_YA_ABIERTA` si ya hay una ABIERTA; inserta la `Vacante` con `creada_en = ahora`; **si había asignado, lo borra del turno (D31)**; escribe `VACANTE_GENERADA` con `datos = {"urgente": bool, "asignado_anterior_id": int | None}`; si es urgente, una `Notificacion` `VACANTE_URGENTE` por cada médico ACTIVO salvo el actor (supuesto 9).

- [ ] **Step 1: Escribir las pruebas que fallan:** `test_el_titular_genera_la_vacante`, `test_el_evento_queda_con_actor_y_datos`, `test_con_asignado_lo_borra_y_lo_deja_en_el_evento` (D31), `test_vacante_con_menos_de_24_h_es_urgente_y_notifica_a_los_medicos_activos` (no al actor, no a coordinadores ni pendientes), `test_vacante_con_mas_de_24_h_no_notifica`, `test_un_tercero_no_puede_generar` (403), `test_el_coordinador_puede_generar_en_un_turno_sin_titular`, `test_un_medico_no_puede_generar_en_un_turno_sin_titular`, `test_turno_empezado_responde_409`, `test_segunda_vacante_abierta_responde_409`, `test_se_puede_generar_otra_despues_de_retirar_la_primera` (preparado con SQL directo hasta la tarea 7), `test_turno_inexistente_responde_404`, `test_dos_generaciones_simultaneas_una_gana` (`commit_real`: una devuelve la vacante, la otra `VACANTE_YA_ABIERTA`).
- [ ] **Step 2: Correr y verificar que fallan:** `python -m pytest tests/test_servicio_vacantes.py -v` → FAIL.
- [ ] **Step 3: Implementar** `generar_vacante`; la garantía de una sola vacante abierta la da `ux_vacante_abierta_por_turno`, el 409 sale de chequear antes y de capturar la violación.
- [ ] **Step 4: Correr y verificar que pasan** → PASS.
- [ ] **Step 5: Commit** `git commit -m "Generar vacante: borra el asignado, registra el evento y notifica las urgentes (D15, D22, D31)"`.

### Task 7: Lote y retiro de vacantes

**Files:**
- Modify: `backend/app/servicios/vacantes.py`
- Test: `backend/tests/test_servicio_vacantes.py`

**Interfaces:**
- Consumes: `generar_vacante` (T6), `bloquear_turnos` (T5), `puede_retirar`, `asignado_a_restaurar` (T4).
- Produces: `generar_lote(sesion, turno_ids: Sequence[str], actor, motivo, reloj, zona) -> list[ResultadoVacante]` (bloquea todos por id ascendente antes de generar; todo o nada, supuesto 8; el `ErrorDominio` que falla lleva el `turno_id` en el mensaje; ids repetidos → 422 `TURNOS_REPETIDOS`); `retirar_vacante(sesion, vacante_id: int, actor, reloj) -> Vacante` (404 `VACANTE_NO_ENCONTRADA`; 409 `VACANTE_NO_ABIERTA` si no está ABIERTA; 403 `SIN_PERMISO`; estado RETIRADA, `cerrada_en = ahora`, evento `VACANTE_RETIRADA`, y restaura el asignado según el supuesto 3).

- [ ] **Step 1: Escribir las pruebas que fallan:** `test_el_lote_genera_una_vacante_por_turno`, `test_un_fallo_del_lote_no_guarda_ninguna` (un turno inexistente en el medio: ninguna vacante ni evento), `test_el_lote_repetido_responde_422`, `test_el_lote_de_dos_vacaciones_simultaneas_no_se_traba` (`commit_real`, ids cruzados en orden inverso), `test_retira_quien_la_genero`, `test_retira_un_coordinador`, `test_un_tercero_no_puede_retirar`, `test_no_se_retira_una_vacante_cubierta_ni_retirada` (409), `test_el_retiro_deja_el_evento`, `test_el_retiro_restaura_al_asignado_que_la_genero` y `test_el_retiro_no_restaura_a_un_asignado_distinto_de_quien_la_genero`.
- [ ] **Step 2: Correr y verificar que fallan** → FAIL.
- [ ] **Step 3: Implementar** ambas funciones.
- [ ] **Step 4: Correr y verificar que pasan** → PASS.
- [ ] **Step 5: Commit** `git commit -m "Lote de vacantes y retiro de vacante (D15, D22)"`.

### Task 8: Rutas reales de vacantes y PR 2

**Files:**
- Create: `backend/app/api/vacantes.py`
- Modify: `backend/app/api/operacion.py` (quitar las tres rutas de vacantes), `backend/app/main.py`, `backend/CLAUDE.md`
- Test: `backend/tests/test_api_vacantes.py`

**Interfaces:**
- Consumes: servicios (T6, T7), esquemas (T1).
- Produces: `POST /api/turnos/{turno_id}/vacantes` (201 `VacanteOut`), `POST /api/vacantes/lote` (201 `LoteVacantesOut`, solo coordinador), `POST /api/vacantes/{id}/retiro` (200 `VacanteOut`). El router hace el commit. `motivo` solo para coordinadores; sin el encabezado `X-Respuesta-Ejemplo`.

- [ ] **Step 1: Escribir las pruebas que fallan:** `test_generar_responde_201_con_el_formato_del_contrato`, `test_el_medico_no_ve_el_motivo_y_el_coordinador_si` (en las tres rutas; foco 4), `test_urgente_se_calcula_en_la_respuesta`, `test_errores_con_codigo_y_status` (parametrizada: `TURNO_NO_ENCONTRADO` 404, `VACANTE_YA_ABIERTA` 409, `SIN_PERMISO` 403, `TURNO_YA_EMPEZO` 409), `test_medico_no_puede_usar_el_lote` (403), `test_sin_token_401`, `test_las_rutas_reales_no_llevan_el_encabezado_de_ejemplo`.
- [ ] **Step 2: Correr y verificar que fallan** → FAIL.
- [ ] **Step 3: Implementar** el router y quitar las rutas de ejemplo correspondientes; actualizar `backend/CLAUDE.md` (orden de bloqueos con `turno`, módulos nuevos).
- [ ] **Step 4: Correr la suite completa** `python -m pytest -q` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Rutas de generar vacante, lote y retiro"`; pushear, abrir el PR contra `main`, pedir revisión, **avisar a Mariano y a Florencia que `app/servicios/vacantes.generar_vacante` ya está disponible** para cerrar staff.

---

# Etapa 3: postulaciones, candidatos y asignación (PR 3)

## Ajustes a la etapa 3 después de F4 y de las reglas del equipo (9/10/2026)

Rama `feature/f3-etapa3`, desde `main` con los PR #12 (F4) y #13 (etapa 2). Estos ajustes completan las tareas 9 a 14 de abajo y prevalecen sobre ellas donde difieran:

1. **Orden de bloqueos (convención 19):** `usuario`, `horario_pactado`, `consolidacion_estado`, `turno`, `vacante`. `asignar` bloquea primero al médico elegido (`bloquear_usuario`), después el turno (`materializar_turno`) y por último la vacante. Postular, retirar la postulación y candidatos no toman bloqueos de usuario explícitos, pero al insertar la postulación y su evento Postgres toma FOR KEY SHARE sobre el médico, después del turno: si a la vez se asigna a ese médico (que lo bloquea primero), una de las dos transacciones puede recibir el deadlock, que responde 409 `CONFLICTO_CONCURRENTE` y se reintenta. Es una limitación conocida; no corrompe datos.
2. **No consolidar:** ninguna de estas operaciones llama a `ponerse_al_dia`; rechazan con 409 `TURNO_TERMINADO` lo que ya terminó (`ahora >= fin`) o está consolidado.
3. **Turno marcado sin cobertura (D19, regla de Florencia):** al asignarlo, en la misma transacción se pone `sin_cobertura_en` en vacío y la vacante `SIN_COBERTURA` pasa a `CUBIERTA` con `cerrada_en = ahora`; el evento de asignación lleva `datos.sin_cobertura_levantada = true`. Un turno marcado sin cobertura cuenta como asignable aunque no tenga vacante ABIERTA. No admite postulaciones: solo se marca cuando ya empezó, y postular exige que no haya empezado (supuestos 4 y 7).
4. **Aviso al asignado:** `notificar` de F4 con un tipo nuevo `TipoNotificacion.TURNO_ASIGNADO` (lista cerrada de `app/dominio/notificaciones.py`, la columna es texto y no necesita migración), destinatario el médico asignado, `datos = {"turnoId", "caso"}`. No se avisa a los demás candidatos (fuera de este plan).
5. **Habilitación (regla de Florencia, supuesto 5):** nadie que sea coordinador, PENDIENTE o BAJA con `fecha_baja` anterior a la fecha del turno se postula ni se lista como candidato ni se asigna.
6. **Bitácora:** `CANDIDATO_ELEGIDO` lleva `posicion`, `candidatos` y `asignado_id`; `ASIGNACION_DIRECTA`, `asignado_id`; `REASIGNACION`, `asignado_id` y `asignado_anterior_id`; `POSTULACION_CREADA` y `POSTULACION_RETIRADA`, `postulacion_id` y `medico_id`.
7. **Motivo de la vacante (D25):** en las respuestas de asignación el motivo de la vacante cerrada se muestra solo a coordinadores; como la asignación es de coordinadores, se ve siempre. Cuando termine esta etapa no queda ninguna ruta con respuesta de ejemplo y se elimina `app/api/operacion.py`.


Rama nueva desde `main` actualizado (con el PR 2 mergeado): `feature/f3-postulaciones-asignacion`.

### Task 9: Reglas puras de habilitación y de caso de asignación

**Files:**
- Create: `backend/app/dominio/asignacion.py`
- Test: `backend/tests/test_asignacion.py`

**Interfaces:**
- Produces: `habilitado_para_turno(rol: RolUsuario, estado: EstadoUsuario, fecha_baja: date | None, fecha_turno: date) -> bool` (supuesto 5); `clasificar_asignacion(tiene_asignado: bool, es_candidato: bool) -> CasoAsignacion` (`REASIGNACION` si ya hay asignado; si no, `CANDIDATO_ELEGIDO` si es candidato; si no, `ASIGNACION_DIRECTA`). `CasoAsignacion` se define en `esquemas_operacion` en la etapa 1; mover aquí a `app/dominio/asignacion.py` e importarlo desde los esquemas, para que el dominio no dependa de la API.

- [ ] **Step 1: Escribir las pruebas que fallan:** coordinador nunca habilitado; PENDIENTE nunca; ACTIVO médico siempre; BAJA con `fecha_turno == fecha_baja` habilitado; BAJA con `fecha_turno = fecha_baja + 1 día` no; BAJA sin `fecha_baja` no (defensivo); los tres casos de `clasificar_asignacion`, con `tiene_asignado=True` ganando sobre `es_candidato`.
- [ ] **Step 2: Correr y verificar que fallan:** `python -m pytest tests/test_asignacion.py -v` → FAIL.
- [ ] **Step 3: Implementar** y mover `CasoAsignacion`.
- [ ] **Step 4: Correr y verificar que pasan,** junto con `tests/test_api_operacion_ejemplos.py` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Reglas de habilitación y caso de asignación (D16, D18, D23, D24)"`.

### Task 10: Guardias de un médico y coberturas del mes

**Files:**
- Create: `backend/app/repos/guardias.py`
- Test: `backend/tests/test_repo_guardias.py`

**Interfaces:**
- Consumes: `calcular_turnos`, `versiones_en_rango`, `realizador_presunto` (quién tiene hoy la guardia: asignado vigente, y si no hay, el titular, salvo vacante abierta o sin cobertura), `Guardia`, `TurnoDelMes`.
- Produces: `guardias_del_medico(sesion: Session, medico_id: int, inicio: datetime, fin: datetime, excluir_turno_id: str, zona: ZoneInfo) -> list[Guardia]`: guardias que se superponen con `[inicio, fin)` en las que el médico es hoy responsable: turnos calculados de la plantilla, reemplazados por la fila guardada cuando existe (foto de D11); excluye el turno evaluado. `turnos_del_mes(sesion, anio: int, mes: int, zona: ZoneInfo) -> list[TurnoDelMes]`: turnos guardados cuyo inicio cae en ese mes de la zona del servicio.

- [ ] **Step 1: Escribir las pruebas que fallan:** `test_incluye_el_turno_calculado_del_titular`, `test_un_turno_con_vacante_abierta_no_cuenta_para_el_titular`, `test_un_turno_asignado_a_otro_no_cuenta_para_el_titular_y_si_para_el_asignado`, `test_usa_la_foto_guardada_y_no_la_plantilla_actual` (foco 3), `test_excluye_el_turno_evaluado`, `test_incluye_la_guardia_que_cruza_medianoche_desde_el_dia_anterior`, `test_turnos_del_mes_respeta_la_zona_del_servicio` (turno del 31/10 22:00 −03:00 cuenta en octubre), `test_turnos_del_mes_ignora_otros_meses`.
- [ ] **Step 2: Correr y verificar que fallan:** `python -m pytest tests/test_repo_guardias.py -v` → FAIL.
- [ ] **Step 3: Implementar** ambas funciones.
- [ ] **Step 4: Correr y verificar que pasan** → PASS.
- [ ] **Step 5: Commit** `git commit -m "Guardias vigentes de un médico y turnos del mes para el orden por equidad (D16, D17)"`.

### Task 11: Postularse y retirar la postulación

**Files:**
- Create: `backend/app/servicios/postulaciones.py`
- Test: `backend/tests/test_servicio_postulaciones.py`

**Interfaces:**
- Consumes: `materializar_turno` (T5), `habilitado_para_turno` (T9), `motivo_inelegibilidad` y `guardias_del_medico` (T10).
- Produces: `postular(sesion, turno_id: str, actor: Usuario, reloj, zona) -> Postulacion` (materializa y bloquea el turno; 403 `NO_HABILITADO` si el actor no es `habilitado_para_turno`; 409 `TURNO_YA_EMPEZO`; 409 `TURNO_SIN_VACANTE` si no hay vacante ABIERTA ni está sin titular, supuesto 4; 422 `NO_ELEGIBLE` con el `Motivo` si no es elegible (D16); crea o reactiva la fila, con `creada_en = ahora`, y escribe `POSTULACION_CREADA`; si ya está activa, 409 `YA_POSTULADO`). `retirar_postulacion(sesion, postulacion_id: int, actor, reloj) -> Postulacion` (404 `POSTULACION_NO_ENCONTRADA`; 403 `SIN_PERMISO` si no es suya ni coordinador; 409 `POSTULACION_YA_RETIRADA`; fija `retirada_en`; evento `POSTULACION_RETIRADA`).

- [ ] **Step 1: Escribir las pruebas que fallan:** `test_un_medico_se_postula_a_un_turno_con_vacante`, `test_postularse_deja_el_evento`, `test_el_titular_no_se_postula_a_su_propio_turno` (`NO_ELEGIBLE`, motivo `ES_TITULAR`), `test_no_se_postula_con_una_guardia_superpuesta`, `test_un_coordinador_no_se_postula`, `test_un_pendiente_no_se_postula`, `test_baja_con_fecha_futura_se_postula_hasta_su_ultimo_dia_y_no_despues` (foco 5), `test_turno_sin_vacante_responde_409`, `test_turno_sin_titular_admite_postulacion_sin_vacante` (materializa el turno), `test_postularse_dos_veces_responde_409`, `test_repostularse_reactiva_la_misma_fila_con_nueva_hora`, `test_retiro_por_el_dueno_y_por_un_coordinador`, `test_un_tercero_no_retira`, `test_dos_postulaciones_simultaneas_del_mismo_medico_dejan_una_fila` (`commit_real`).
- [ ] **Step 2: Correr y verificar que fallan** → FAIL.
- [ ] **Step 3: Implementar** ambas funciones.
- [ ] **Step 4: Correr y verificar que pasan** → PASS.
- [ ] **Step 5: Commit** `git commit -m "Postularse a un turno y retirar la postulación (D16, D22)"`.

### Task 12: Candidatos ordenados por equidad

**Files:**
- Modify: `backend/app/servicios/postulaciones.py`
- Test: `backend/tests/test_servicio_postulaciones.py`

**Interfaces:**
- Consumes: `ordenar_candidatos`, `contar_coberturas`, `horas_en_semana`, `motivo_inelegibilidad`, `turnos_del_mes`, `guardias_del_medico`.
- Produces: `@dataclass(frozen=True) CandidatoCalculado(posicion: int | None, medico: Usuario, postulado_en: datetime, coberturas_mes: int, horas_semana: float, elegible: bool, motivo: Motivo | None)` y `listar_candidatos(sesion, turno_id: str, zona) -> list[CandidatoCalculado]`: postulaciones no retiradas de médicos habilitados para ese turno (los demás no aparecen), elegibles ordenados por D17 con `posicion` 1..n y, a continuación, los no elegibles con `posicion=None`; no materializa el turno (404 si no existe).

- [ ] **Step 1: Escribir las pruebas que fallan:** `test_ordena_por_menos_coberturas_en_el_mes_del_turno`, `test_desempata_por_hora_de_postulacion`, `test_las_horas_de_la_semana_no_cambian_el_orden`, `test_los_no_elegibles_van_al_final_con_su_motivo`, `test_un_impedimento_que_desaparece_vuelve_elegible` (D16: retirar la vacante conflictiva y volver a pedir), `test_no_lista_postulaciones_retiradas`, `test_no_lista_a_un_medico_dado_de_baja_para_un_turno_posterior_a_su_baja`, `test_un_turno_sin_postulantes_devuelve_lista_vacia`, `test_turno_inexistente_responde_404`.
- [ ] **Step 2: Correr y verificar que fallan** → FAIL.
- [ ] **Step 3: Implementar** `listar_candidatos`.
- [ ] **Step 4: Correr y verificar que pasan** → PASS.
- [ ] **Step 5: Commit** `git commit -m "Lista de candidatos ordenada por equidad (D16, D17)"`.

### Task 13: Asignar

**Files:**
- Create: `backend/app/servicios/asignacion.py`
- Test: `backend/tests/test_servicio_asignacion.py`

**Interfaces:**
- Consumes: `materializar_turno`, `listar_candidatos` (T12), `habilitado_para_turno`, `clasificar_asignacion` (T9).
- Produces: `@dataclass(frozen=True) ResultadoAsignacion(turno: Turno, asignado: Usuario, caso: CasoAsignacion, vacante: Vacante | None)` y `asignar(sesion, turno_id: str, medico_id: int, reasignar: bool, actor: Usuario, reloj, zona) -> ResultadoAsignacion` (solo coordinador, 403 `SIN_PERMISO`). Bloquea el turno y luego al médico elegido (404 `USUARIO_NO_ENCONTRADO`); 409 `TURNO_TERMINADO` si `ahora >= fin`; 422 `NO_HABILITADO`; 422 `ES_TITULAR`; 422 `CANDIDATO_NO_ELEGIBLE` con el motivo (supuesto 6); 409 `YA_ASIGNADO` si ya es el asignado; 409 `YA_TIENE_ASIGNADO` si hay asignado y no `reasignar`; 409 `TURNO_SIN_VACANTE` si no hay vacante ABIERTA, ni asignado, ni está sin titular. Fija `asignado_id`, cierra la vacante ABIERTA como CUBIERTA con `cerrada_en = ahora` y escribe `CANDIDATO_ELEGIDO` (`datos = {"posicion": int, "candidatos": int}`), `ASIGNACION_DIRECTA` o `REASIGNACION` (`datos = {"asignado_anterior_id": int}`).

- [ ] **Step 1: Escribir las pruebas que fallan:** `test_elige_a_un_candidato_y_registra_posicion_y_cantidad`, `test_el_coordinador_puede_elegir_al_ultimo_de_la_lista`, `test_asignacion_directa_de_quien_no_se_postulo`, `test_reasignacion_pide_reasignar_true_y_registra_al_anterior`, `test_sin_reasignar_responde_409`, `test_cierra_la_vacante_como_cubierta`, `test_asignar_a_un_turno_sin_titular_no_necesita_vacante`, `test_no_asigna_a_un_coordinador_ni_a_un_pendiente`, `test_no_asigna_al_titular`, `test_no_asigna_con_una_guardia_superpuesta`, `test_no_asigna_a_un_baja_despues_de_su_fecha_de_baja`, `test_turno_terminado_responde_409`, `test_un_medico_no_puede_asignar`, `test_las_postulaciones_sobreviven_a_la_asignacion` (D16), `test_dos_asignaciones_simultaneas_una_gana` (`commit_real`: la segunda `YA_TIENE_ASIGNADO`), `test_postulacion_y_asignacion_simultaneas_no_dejan_estado_incoherente` (`commit_real`, foco 1).
- [ ] **Step 2: Correr y verificar que fallan** → FAIL.
- [ ] **Step 3: Implementar** `asignar`.
- [ ] **Step 4: Correr y verificar que pasan** → PASS.
- [ ] **Step 5: Commit** `git commit -m "Asignación con sus tres casos: candidato, directa y reasignación (D17, D18, D22)"`.

### Task 14: Rutas reales, decisiones y PR 3

**Files:**
- Create: `backend/app/api/postulaciones.py`, `backend/app/api/asignacion.py`
- Delete: `backend/app/api/operacion.py`; quitar su registro de `main.py`
- Modify: `docs/decisiones-arquitectura.md` (D32 en adelante con los supuestos aprobados), `CLAUDE.md` (quitar la nota del encabezado de ejemplo), `backend/CLAUDE.md`, `docs/prompts-principales.md`
- Test: `backend/tests/test_api_postulaciones.py`, `backend/tests/test_api_asignacion.py`

**Interfaces:**
- Produces: `POST /api/turnos/{id}/postulaciones` (201), `POST /api/postulaciones/{id}/retiro` (200), `GET /api/turnos/{id}/candidatos` (200, solo coordinador), `PUT /api/turnos/{id}/asignacion` (200, solo coordinador), con los esquemas de T1.

- [ ] **Step 1: Escribir las pruebas que fallan:** una por ruta con su respuesta en el formato del contrato; `test_el_flujo_completo` (el titular genera la vacante, dos médicos se postulan, el coordinador consulta candidatos, asigna al segundo y el calendario/turno refleja el asignado); `test_un_medico_no_puede_ver_candidatos_ni_asignar` (403); `test_codigos_y_status_de_error` (parametrizada); `test_sin_token_401`; `test_ya_no_quedan_rutas_de_ejemplo` (ninguna respuesta lleva `X-Respuesta-Ejemplo`).
- [ ] **Step 2: Correr y verificar que fallan** → FAIL.
- [ ] **Step 3: Implementar** los routers, eliminar el módulo de ejemplos y actualizar la documentación.
- [ ] **Step 4: Correr la suite completa** `python -m pytest -q` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Rutas de postulaciones, candidatos y asignación; fin de las respuestas de ejemplo"`; pushear, abrir el PR 3 contra `main`, pedir revisión a otra persona del equipo.
