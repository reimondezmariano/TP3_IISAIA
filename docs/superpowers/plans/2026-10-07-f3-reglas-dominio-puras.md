# F3 (primera etapa): reglas de dominio puras. Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Objetivo:** implementar en `backend/app/dominio/` las reglas de elegibilidad (D16), orden por equidad (D17), consolidación (D20), alertas escalonadas (D19) y vacante urgente (D15) como funciones puras con pruebas pytest.

**Arquitectura:** un módulo por regla, siguiendo `app/dominio/calendario.py`: dataclasses inmutables como entrada y salida, funciones sin estado, sin base de datos ni FastAPI. Lo que depende de "ahora" recibe `ahora` como parámetro (D27); los módulos nunca consultan el reloj. Los repos y endpoints que las usen quedan para etapas posteriores.

**Tecnologías:** Python 3.12, pytest. Sin dependencias nuevas.

**Spec:** no hay spec propio; las reglas están en `docs/decisiones-arquitectura.md`, decisiones D15 a D22 y D27.

## Restricciones globales

- Solo `backend/app/dominio/` y `backend/tests/`. No se crean modelos, migraciones ni repos: los modelos los hace Florencia en `feature/f2-cimientos`. Los módulos nuevos no importan nada de `app.modelos`, `app.repos`, `app.db` ni `fastapi`.
- Nada en `backend/app/` consulta la hora del sistema (D27); `tests/test_sin_hora_del_sistema.py` lo verifica.
- Todo instante es `datetime` con zona horaria; una entrada sin zona lanza `ValueError` (igual que `RelojFijo`). Zona del servicio: `America/Argentina/Buenos_Aires`.
- Vigencia de los umbrales y plazos en horas exactas; los límites se evalúan como se indica en cada tarea.
- La semana empieza el lunes (D13).
- Pruebas sin base de datos (no usan las fixtures `sesion` ni `cliente`); corren con `python -m pytest` desde `backend/` con el venv activo (`.venv/Scripts/python` en Windows).
- Commits chicos, en español, con la decisión citada. Cada commit termina con la línea `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Un commit por tarea, en la branch `feature/f3-reglas-dominio`.

## Supuestos (decididos acá; confirmar en la revisión)

1. Los datos de entrada los arma quien llama (la capa de repos de una etapa posterior); las funciones no consultan nada.
2. "Anticipación menor a 24 h" (D15) es estricta: exactamente 24 h no es urgente.
3. Cobertura para D17: turno del mes calendario (zona del servicio, por fecha de inicio) con asignado distinto del titular, incluso si el turno no tiene titular (baja, D24).
4. Una alerta (D19) se emite solo si el instante del umbral cae dentro del período en que la vacante estuvo abierta y mientras el turno no terminó. Una vacante abierta 10 h antes del inicio no dispara las de 48 h ni 24 h.
5. **Resuelto con el equipo (D31).** Realizador presunto (D20): con una vacante abierta o `sin_cobertura`, ninguno (D19); si no, el asignado vigente; si no hay asignado, el titular. Esto reemplaza la prioridad original (asignado antes que vacante abierta). La regla de fondo, borrar el asignado en la misma transacción que genera la vacante y registrarlo en la bitácora con VACANTE_GENERADA, se implementa en el endpoint de generar vacante, que es la próxima etapa; la prioridad de la consolidación es solo una defensa.
6. La elegibilidad (D16) cubre solo las dos reglas de D16 (titular y guardia superpuesta). Rol y estado del usuario (D23) los filtra quien arme la lista de candidatos.

## Foco de revisión

1. **Instante exacto en cada borde:** vacante a exactamente 24 h (no urgente), `ahora` igual a un umbral (dispara), turno que termina justo cuando empieza otro (no se superpone), `ahora` igual al fin (consolida).
2. **Datetime sin zona:** debe fallar con `ValueError`, no comparar mal. Prueba en la tarea 1 y en cada función que recibe instantes.
3. **Candidato sin coberturas en el mapa:** cuenta como 0, no `KeyError`. Prueba en la tarea 4.
4. **Empate total** (mismas coberturas y misma hora de postulación): el orden es estable por `medico_id`. Prueba en la tarea 4.
5. **Consolidar dos veces:** la segunda corrida no devuelve nada (idempotencia, D20), y un turno rectificado no se vuelve a consolidar. Prueba en la tarea 6.

---

## Estructura de archivos

```
backend/app/dominio/tiempo.py          (T1)  exigir_zona
backend/app/dominio/vacantes.py        (T1)  es_urgente
backend/app/dominio/alertas.py         (T2)  Umbral, alertas_pendientes
backend/app/dominio/elegibilidad.py    (T3)  Motivo, Guardia, motivo_inelegibilidad
backend/app/dominio/equidad.py         (T4, T5)  Candidato, contar_coberturas, ordenar_candidatos, horas_en_semana
backend/app/dominio/consolidacion.py   (T6)  TurnoConsolidable, Consolidacion, consolidar
backend/tests/test_vacantes.py, test_alertas.py, test_elegibilidad.py, test_equidad.py, test_consolidacion.py
docs/prompts-principales.md            (T7)
```

---

### Task 1: Vacante urgente (D15)

**Files:**
- Create: `backend/app/dominio/tiempo.py`, `backend/app/dominio/vacantes.py`
- Test: `backend/tests/test_vacantes.py`

**Interfaces:**
- Produces: `exigir_zona(*instantes: datetime) -> None` (lanza `ValueError` si alguno no tiene zona); `es_urgente(inicio_turno: datetime, generada_en: datetime) -> bool`. Las demás tareas importan `exigir_zona` de `app.dominio.tiempo`.

- [ ] **Step 1: Escribir las pruebas que fallan** en `test_vacantes.py`, con `INICIO = datetime(2026, 10, 17, 8, tzinfo=ZONA)`:
  - `test_con_mas_de_24_horas_no_es_urgente`: generada 24 h 1 min antes → `False`
  - `test_a_exactamente_24_horas_no_es_urgente` → `False`
  - `test_con_menos_de_24_horas_es_urgente`: 23 h 59 min antes → `True`
  - `test_generada_con_el_turno_en_curso_es_urgente`: 1 h después del inicio → `True`
  - `test_instante_sin_zona_es_error`: `pytest.raises(ValueError)` con `datetime(2026, 10, 16, 9)` como `generada_en`
- [ ] **Step 2: Correr y verificar que fallan**

  Run: `python -m pytest tests/test_vacantes.py -v` → FAIL (`ModuleNotFoundError`).
- [ ] **Step 3: Implementar** `exigir_zona` en `tiempo.py` y `es_urgente` en `vacantes.py` (`inicio_turno - generada_en < timedelta(hours=24)`; constante `UMBRAL_URGENTE` con la cita a D15).
- [ ] **Step 4: Correr y verificar que pasan**

  Run: `python -m pytest tests/test_vacantes.py tests/test_sin_hora_del_sistema.py -v` → PASS.
- [ ] **Step 5: Commit**

  ```bash
  git add backend/app/dominio/tiempo.py backend/app/dominio/vacantes.py backend/tests/test_vacantes.py
  git commit -m "Vacante urgente con menos de 24 h de anticipación (D15)"
  ```

---

### Task 2: Alertas escalonadas (D19)

**Files:**
- Create: `backend/app/dominio/alertas.py`
- Test: `backend/tests/test_alertas.py`

**Interfaces:**
- Consumes: `exigir_zona` (T1).
- Produces: `class Umbral(Enum)` con `HORAS_48`, `HORAS_24`, `INICIO` (valores de texto `"HORAS_48"`, `"HORAS_24"`, `"INICIO"`, en ese orden cronológico); `alertas_pendientes(inicio: datetime, fin: datetime, vacante_abierta_desde: datetime, ahora: datetime, enviadas: Collection[Umbral]) -> list[Umbral]`, ordenada cronológicamente.

Regla: el instante de cada umbral es `inicio - 48 h`, `inicio - 24 h`, `inicio`. Un umbral está pendiente si no está en `enviadas`, su instante es `>= vacante_abierta_desde`, es `<= ahora` y `ahora < fin`.

- [ ] **Step 1: Escribir las pruebas que fallan**, con `INICIO = datetime(2026, 10, 17, 8, tzinfo=ZONA)`, `FIN = INICIO + 12 h`, vacante abierta 10 días antes salvo que se indique:
  - `test_antes_de_48_horas_no_hay_alertas` (`ahora` = inicio − 48 h 1 min) → `[]`
  - `test_a_las_48_horas_exactas_dispara_la_primera` → `[Umbral.HORAS_48]`
  - `test_a_las_24_horas_con_la_primera_enviada_dispara_solo_la_segunda` → `[Umbral.HORAS_24]`
  - `test_al_inicio_dispara_la_tercera` (enviadas 48 y 24) → `[Umbral.INICIO]`
  - `test_sin_enviadas_y_ya_en_el_inicio_devuelve_los_tres_en_orden` → `[HORAS_48, HORAS_24, INICIO]`
  - `test_no_repite_un_umbral_ya_enviado` (los tres enviados) → `[]`
  - `test_vacante_abierta_a_10_horas_solo_dispara_el_inicio`: `vacante_abierta_desde` = inicio − 10 h, `ahora` = inicio → `[Umbral.INICIO]`
  - `test_vacante_abierta_justo_en_el_umbral_lo_incluye`: abierta en inicio − 24 h, `ahora` = inicio − 24 h → `[Umbral.HORAS_24]`
  - `test_turno_terminado_no_alerta`: `ahora` = `FIN` → `[]`
  - `test_instante_sin_zona_es_error`
- [ ] **Step 2: Correr y verificar que fallan:** `python -m pytest tests/test_alertas.py -v` → FAIL.
- [ ] **Step 3: Implementar** `Umbral` y `alertas_pendientes` en `alertas.py`; tabla interna `{Umbral: timedelta}` con los desfasajes 48 h, 24 h y 0.
- [ ] **Step 4: Correr y verificar que pasan:** `python -m pytest tests/test_alertas.py -v` → PASS.
- [ ] **Step 5: Commit**

  ```bash
  git add backend/app/dominio/alertas.py backend/tests/test_alertas.py
  git commit -m "Umbrales de alerta de 48 h, 24 h e inicio para turnos sin cobertura (D19)"
  ```

---

### Task 3: Elegibilidad de postulantes (D16)

**Files:**
- Create: `backend/app/dominio/elegibilidad.py`
- Test: `backend/tests/test_elegibilidad.py`

**Interfaces:**
- Consumes: `exigir_zona` (T1).
- Produces: `class Motivo(Enum)` con `ES_TITULAR`, `GUARDIA_SUPERPUESTA`; `@dataclass(frozen=True) class Guardia: inicio: datetime; fin: datetime`; `motivo_inelegibilidad(medico_id: int, titular_id: int | None, inicio: datetime, fin: datetime, guardias_del_medico: Iterable[Guardia]) -> Motivo | None` (`None` = elegible); `es_elegible(...)` con los mismos parámetros → `bool`.

Regla: `ES_TITULAR` si `medico_id == titular_id` (tiene prioridad sobre el otro motivo). `GUARDIA_SUPERPUESTA` si alguna guardia cumple `g.inicio < fin and g.fin > inicio`. `guardias_del_medico` son las guardias vigentes del médico (titular sin vacante abierta o asignado), sin incluir el turno evaluado; armarla es responsabilidad de quien llama. Al recalcularse en cada consulta, un impedimento que desaparece vuelve elegible al médico sin estado guardado.

- [ ] **Step 1: Escribir las pruebas que fallan**, con turno 17/10 08:00–20:00:
  - `test_medico_libre_es_elegible` (sin guardias) → `None`
  - `test_titular_no_se_postula_a_su_propio_turno` → `Motivo.ES_TITULAR`
  - `test_turno_sin_titular_no_impide_a_nadie` (`titular_id=None`) → `None`
  - `test_guardia_que_se_superpone_parcialmente_impide` (06:00–10:00) → `GUARDIA_SUPERPUESTA`
  - `test_guardia_contenida_en_el_turno_impide` (10:00–12:00)
  - `test_guardia_que_contiene_al_turno_impide` (00:00–23:59)
  - `test_guardia_que_termina_cuando_empieza_el_turno_no_impide` (00:00–08:00) → `None`
  - `test_guardia_que_empieza_cuando_termina_el_turno_no_impide` (20:00–23:00) → `None`
  - `test_guardia_que_cruza_medianoche_impide`: guardia 16/10 22:00 – 17/10 09:00 → `GUARDIA_SUPERPUESTA`
  - `test_titular_y_superpuesta_informa_titular`
  - `test_al_desaparecer_el_impedimento_vuelve_a_ser_elegible`: misma consulta con y sin la guardia (D16)
  - `test_es_elegible_refleja_el_motivo`
  - `test_instante_sin_zona_es_error`
- [ ] **Step 2: Correr y verificar que fallan:** `python -m pytest tests/test_elegibilidad.py -v` → FAIL.
- [ ] **Step 3: Implementar** las funciones y tipos en `elegibilidad.py`.
- [ ] **Step 4: Correr y verificar que pasan:** `python -m pytest tests/test_elegibilidad.py -v` → PASS.
- [ ] **Step 5: Commit**

  ```bash
  git add backend/app/dominio/elegibilidad.py backend/tests/test_elegibilidad.py
  git commit -m "Elegibilidad de postulantes: no titular ni guardia superpuesta (D16)"
  ```

---

### Task 4: Orden de candidatos por equidad (D17)

**Files:**
- Create: `backend/app/dominio/equidad.py`
- Test: `backend/tests/test_equidad.py`

**Interfaces:**
- Consumes: `exigir_zona` (T1).
- Produces:
  - `@dataclass(frozen=True) class Candidato: medico_id: int; postulado_en: datetime`
  - `@dataclass(frozen=True) class TurnoDelMes: inicio: datetime; asignado_id: int | None; titular_id: int | None`
  - `contar_coberturas(turnos: Iterable[TurnoDelMes], anio: int, mes: int, zona: ZoneInfo) -> dict[int, int]`: por médico, cantidad de turnos cuyo `inicio`, convertido a `zona`, cae en ese mes, con `asignado_id` no nulo y distinto de `titular_id`.
  - `ordenar_candidatos(candidatos: Iterable[Candidato], coberturas: Mapping[int, int]) -> list[Candidato]`: clave `(coberturas.get(medico_id, 0), postulado_en, medico_id)` ascendente.

- [ ] **Step 1: Escribir las pruebas que fallan** (zona `America/Argentina/Buenos_Aires`):
  - `test_gana_quien_cubrio_menos` (coberturas {1: 3, 2: 1, 3: 2}) → orden 2, 3, 1
  - `test_la_equidad_manda_sobre_la_hora_de_postulacion`: el que cubrió menos pero se postuló último queda primero
  - `test_desempata_por_hora_de_postulacion`
  - `test_medico_ausente_del_mapa_cuenta_cero` (sin `KeyError`, queda primero frente a quien tiene 1)
  - `test_empate_total_se_ordena_por_medico_id`
  - `test_lista_vacia_devuelve_lista_vacia`
  - `test_no_modifica_la_entrada` (la entrada original no se reordena)
  - `test_cuenta_cobertura_si_asignado_no_es_titular`
  - `test_no_cuenta_el_turno_que_hace_su_titular` (asignado == titular)
  - `test_no_cuenta_turno_sin_asignado`
  - `test_cuenta_cobertura_de_turno_sin_titular` (supuesto 3)
  - `test_solo_cuenta_el_mes_pedido`: turnos de septiembre, octubre y noviembre; se pide octubre
  - `test_el_mes_se_mide_en_la_zona_del_servicio`: turno 31/10 22:00 −03:00 (= 01/11 01:00 UTC) cuenta en octubre; turno 01/11 00:30 −03:00 cuenta en noviembre
  - `test_acumula_varias_coberturas_del_mismo_medico`
  - `test_instante_sin_zona_es_error` (en `postulado_en` y en `TurnoDelMes.inicio`)
- [ ] **Step 2: Correr y verificar que fallan:** `python -m pytest tests/test_equidad.py -v` → FAIL.
- [ ] **Step 3: Implementar** `Candidato`, `TurnoDelMes`, `contar_coberturas` y `ordenar_candidatos` en `equidad.py`.
- [ ] **Step 4: Correr y verificar que pasan:** `python -m pytest tests/test_equidad.py -v` → PASS.
- [ ] **Step 5: Commit**

  ```bash
  git add backend/app/dominio/equidad.py backend/tests/test_equidad.py
  git commit -m "Orden de candidatos por equidad: menos coberturas en el mes, luego postulación (D17)"
  ```

---

### Task 5: Horas de guardia en la semana (dato informativo de D17)

**Files:**
- Modify: `backend/app/dominio/equidad.py`
- Test: `backend/tests/test_equidad.py`

**Interfaces:**
- Consumes: `Guardia` (T3), `exigir_zona` (T1).
- Produces: `horas_en_semana(guardias: Iterable[Guardia], dia_referencia: date, zona: ZoneInfo) -> float`: horas de las guardias que caen dentro de la semana (lunes 00:00 a lunes siguiente 00:00, en `zona`) que contiene `dia_referencia`; las guardias que cruzan el borde de la semana se prorratean. No interviene en `ordenar_candidatos`.

- [ ] **Step 1: Escribir las pruebas que fallan** (semana del lunes 12/10/2026 al domingo 18/10):
  - `test_suma_las_guardias_de_la_semana` (8 h + 12 h → `20.0`)
  - `test_ignora_guardias_de_otra_semana`
  - `test_guardia_que_cruza_el_domingo_se_prorratea`: domingo 18/10 20:00 → lunes 19/10 08:00 → `4.0` en esa semana y `8.0` en la siguiente
  - `test_la_referencia_puede_ser_cualquier_dia_de_la_semana` (lunes y domingo dan lo mismo)
  - `test_sin_guardias_son_cero_horas` → `0.0`
  - `test_instante_sin_zona_es_error`
- [ ] **Step 2: Correr y verificar que fallan:** `python -m pytest tests/test_equidad.py -k semana -v` → FAIL.
- [ ] **Step 3: Implementar** `horas_en_semana` en `equidad.py`; el lunes de la semana como en `calendario._lunes`, no duplicar la lógica de días si se puede reutilizar sin importar un nombre privado (extraer a `tiempo.py` si hace falta).
- [ ] **Step 4: Correr y verificar que pasan:** `python -m pytest tests/test_equidad.py -v` → PASS.
- [ ] **Step 5: Commit**

  ```bash
  git add backend/app/dominio backend/tests/test_equidad.py
  git commit -m "Horas de guardia del médico en la semana como dato informativo (D17)"
  ```

---

### Task 6: Consolidación (D20)

**Files:**
- Create: `backend/app/dominio/consolidacion.py`
- Test: `backend/tests/test_consolidacion.py`

**Interfaces:**
- Consumes: `exigir_zona` (T1).
- Produces:
  - `@dataclass(frozen=True) class TurnoConsolidable: turno_id: int; fin: datetime; titular_id: int | None; asignado_id: int | None; hay_vacante_abierta: bool; sin_cobertura: bool; consolidado_en: datetime | None`
  - `@dataclass(frozen=True) class Consolidacion: turno_id: int; realizador_id: int | None; consolidado_en: datetime`
  - `realizador_presunto(titular_id, asignado_id, hay_vacante_abierta, sin_cobertura) -> int | None` según el supuesto 5.
  - `consolidar(turnos: Iterable[TurnoConsolidable], ahora: datetime) -> list[Consolidacion]`: un resultado por cada turno con `consolidado_en is None` y `fin <= ahora`, con `consolidado_en=ahora`, en el orden de entrada. Idempotente: lo ya consolidado (incluso rectificado) no se devuelve.

- [ ] **Step 1: Escribir las pruebas que fallan**:
  - `test_turno_terminado_lo_hace_el_titular` (sin vacante) → realizador = titular
  - `test_turno_cubierto_lo_hace_el_asignado` (asignado ≠ titular) → asignado
  - `test_vacante_abierta_sin_asignado_queda_sin_realizador` → `None`
  - `test_sin_cobertura_queda_sin_realizador_aunque_haya_titular` → `None`
  - `test_turno_sin_titular_y_sin_asignado_queda_sin_realizador` (baja sin cubrir) → `None`
  - `test_turno_sin_titular_cubierto_lo_hace_el_asignado`
  - `test_turno_en_curso_no_se_consolida` (`fin` > `ahora`) → `[]`
  - `test_turno_que_termina_justo_ahora_se_consolida` (`fin == ahora`)
  - `test_ya_consolidado_no_se_repite`: segunda llamada con los resultados reflejados en `consolidado_en` → `[]` (D20, idempotencia)
  - `test_turno_rectificado_no_se_vuelve_a_consolidar` (`consolidado_en` ya seteado con otro realizador en la fila)
  - `test_consolida_varios_y_deja_los_pendientes` (mezcla de terminados, en curso y ya consolidados)
  - `test_instante_sin_zona_es_error`
- [ ] **Step 2: Correr y verificar que fallan:** `python -m pytest tests/test_consolidacion.py -v` → FAIL.
- [ ] **Step 3: Implementar** los tipos, `realizador_presunto` y `consolidar` en `consolidacion.py`.
- [ ] **Step 4: Correr y verificar que pasan** junto con toda la suite pura: `python -m pytest tests/test_vacantes.py tests/test_alertas.py tests/test_elegibilidad.py tests/test_equidad.py tests/test_consolidacion.py tests/test_calendario.py tests/test_sin_hora_del_sistema.py -v` → PASS.
- [ ] **Step 5: Commit**

  ```bash
  git add backend/app/dominio/consolidacion.py backend/tests/test_consolidacion.py
  git commit -m "Consolidación perezosa e idempotente de turnos terminados (D20)"
  ```

---

### Task 7: Registro del prompt

**Files:**
- Modify: `docs/prompts-principales.md` (nueva sección "4. F3: reglas de dominio puras", antes de "Próximas entradas")

- [ ] **Step 1: Agregar la sección** con fecha 7/10/2026, herramienta (Claude Code con Superpowers, `writing-plans`), el prompt de arranque, y el resultado: plan en `docs/superpowers/plans/2026-10-07-f3-reglas-dominio-puras.md`, branch `feature/f3-reglas-dominio`, alcance solo de funciones puras (los modelos son de `feature/f2-cimientos`).
- [ ] **Step 2: Correr la suite pura** (comando de la tarea 6) → PASS.
- [ ] **Step 3: Commit**

  ```bash
  git add docs/prompts-principales.md
  git commit -m "Registrar el prompt de las reglas de dominio puras (F3)"
  ```
