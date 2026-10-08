# F5: staff, backend. Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Objetivo:** la API de la pantalla de staff (D26), solo para coordinadores: listar usuarios con rol, estado y horarios vigentes; activar un médico pendiente; cargar un horario pactado; modificarlo con una versión nueva y devolver los turnos afectados (D12); cerrarlo; cambiar el rol respetando D23; dar de baja a un médico (D24) y designar un titular nuevo en un horario sin titular.

**Arquitectura:** dos routers nuevos (`app/api/usuarios.py` y `app/api/horarios.py`) que validan la entrada y delegan en una capa nueva, `app/servicios/`, que combina las reglas puras de `app/dominio/plantilla.py` con las consultas de `app/repos/`. Los servicios no hacen commit; el router confirma la transacción. Cada cambio de plantilla parte la versión que rige en la fecha pedida y abre una nueva que hereda su fin de vigencia (D10); los turnos ya guardados conservan su foto (D11) y se devuelven como "turnos afectados" (D12). La concurrencia se resuelve con bloqueos de filas (`SELECT ... FOR UPDATE`) siempre en el mismo orden, usuario y después horario, y con la restricción de exclusión que ya existe como respaldo (regla 8). Una sola migración nueva, la `0003`, agrega la coherencia entre estado BAJA y fecha de baja.

**Tecnologías:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, psycopg 3, pytest.

**Spec:** no hay spec propio de F5, igual que en F2. El plan se apoya en `docs/decisiones-arquitectura.md` (D10, D11, D12, D14, D22, D23, D24, D26, D27, D30) y en el `CLAUDE.md` de la raíz. Lo que esas decisiones dejan abierto está en "Decisiones de este plan".

**Branch:** `feature/f5-staff-backend`, creada desde `feature/f2-cimientos` (todavía sin mergear en main). El pull request de F5 se abre contra main después de mergear el #7.

**Ejecución:** a definir por el equipo al aprobar el plan. Un commit por tarea. Al terminar las tareas 1 a 10, revisión de código de toda la branch (superpowers:requesting-code-review) antes del pull request. La tarea 11 depende de F2b y se ejecuta aparte (ver la tarea).

## Restricciones globales

- No se toca nada de vacantes, postulaciones ni consolidación: es de Mariano (F2b, F3, F4). F5 solo **lee** `turno` para listar turnos afectados y coberturas. La única escritura sobre vacantes es la tarea 11, y pasa por la función de Mariano.
- Toda la API va bajo `/api`. Todos los endpoints nuevos exigen `requiere_coordinador` (regla 7). Errores `{"codigo", "mensaje"}`: 401 sin sesión, 403 sin permiso, 404 inexistente, 409 conflicto de estado o concurrencia, 422 regla de negocio o validación (`VALIDACION`).
- JSON en camelCase mediante `app/api/esquemas.py::Esquema`. Instantes en ISO 8601 con desplazamiento de Buenos Aires (`2026-10-20T08:00:00-03:00`).
- "Hoy" sale siempre de `hoy(reloj)` (tarea 1), nunca de la hora del sistema (D27, regla 10).
- Nunca se borra un usuario ni una versión de horario (D24, D10). Las versiones solo se cierran (`vigente_hasta`) o se agregan.
- Orden de bloqueos en toda la capa de servicios: primero filas de `usuario`, después filas de `horario_pactado`. Varios usuarios se bloquean en un solo SELECT ordenado por id.
- Un turno ya guardado nunca se recalcula (D11, D12).
- La migración nueva es la `0003` y sigue a la `0002` de F2. SQL escrito a mano con `op.execute`; el modelo SQLAlchemy tiene que coincidir.
- Pruebas siempre contra el Postgres local de docker-compose (puerto 5433). Comandos del backend desde `backend/`.
- Un commit por tarea, en español, citando las decisiones. Cada commit termina con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Decisiones de este plan

Elecciones que las decisiones de arquitectura dejan abiertas. La 1 resuelve una ambigüedad dentro de D24 y necesita aprobación explícita del equipo. Las 2, 4 y 13 agregan o cambian algo del CLAUDE.md o de D23 y D24, y se documentan en la tarea 10.

1. **Fecha de baja = último día activo (D24).** D24 dice "activo hasta ese día inclusive" y también "sus horarios quedan sin titular desde la fecha de baja". Las dos frases no pueden valer a la vez para la guardia de ese día. Este plan toma la primera: el médico hace su guardia del día de la baja, y la versión sin titular empieza el **día siguiente**.
2. **Baja programada.** `POST /usuarios/{id}/baja` acepta una fecha de hoy en adelante, nunca anterior (no se reescribe la historia). El estado pasa a BAJA en el momento de registrar la baja, así la pantalla de staff la muestra enseguida, pero la cuenta sigue entrando hasta la fecha de baja inclusive: `usuario_actual` rechaza una BAJA solo si `fecha_baja < hoy`. La migración `0003` obliga a que BAJA y `fecha_baja` vayan juntas.
3. **Baja solo de médicos.** Un coordinador que deja el servicio pasa antes a médico (y ahí rige "al menos un coordinador activo"). Así D23 se valida en un solo lugar.
4. **Médico que pasa a coordinador: sus horarios quedan sin titular en la misma transacción**, desde mañana (el mismo criterio de la decisión 1: hoy todavía hace su guardia). D23 dice "deja antes sus horarios sin titular": hacerlo en la misma acción garantiza que nunca exista un coordinador titular, y reutiliza el mecanismo de la baja. Si tiene una versión futura propia en algún horario, se rechaza con 409 y el coordinador la resuelve antes.
5. **Al menos un coordinador activo (D23), con bloqueo de filas y no con un trigger.** Un trigger diferido que cuente coordinadores al confirmar ve fotos viejas bajo READ COMMITTED: dos degradaciones simultáneas podrían confirmar las dos. En cambio, un único `SELECT ... WHERE id = :objetivo OR (rol = COORDINADOR AND estado = ACTIVO) ORDER BY id FOR UPDATE` serializa los cambios de rol. El segundo, al despertar, vuelve a evaluar el WHERE y ya no cuenta a quien dejó de ser coordinador. Sigue siendo la base la que resuelve la carrera (regla 8). Lo prueba un test `commit_real`.
6. **Ningún cambio de plantilla en el pasado.** La fecha `desde` de una versión nueva, de un cierre o del alta de un horario tiene que ser hoy o posterior (422 `FECHA_PASADA`). Si no, cambiarían turnos pasados calculados que nunca se guardaron.
7. **La versión nueva parte la versión que rige en `desde` y hereda su fin de vigencia.** Si el horario tiene una renegociación ya programada (por ejemplo, desde el 2/11), un cambio desde el 20/10 rige solo hasta el 2/11 y la versión programada queda intacta. Errores: no hay versión que rija ese día (cerrado o todavía no empezó), 409 `HORARIO_SIN_VIGENCIA`; ya hay una versión que empieza justo ese día, 409 `VERSION_EN_ESA_FECHA`.
8. **Una sola ruta para modificar y para designar titular:** `POST /horarios/{id}/versiones` con `desde` y solo los campos que cambian. Lo que se omite se copia de la versión que se parte; `medicoId: null` deja el horario sin titular. Designar un titular nuevo en un horario BAJA es `{desde, medicoId}`. Si el resultado es igual a la versión vigente, 422 `SIN_CAMBIOS`.
9. **Turnos afectados (D12):** los turnos **guardados** (con vacante, asignación o marca sin cobertura) de los horarios tocados, con fecha desde `desde` y sin consolidar. Conservan su foto (inicio, fin, titular) y se devuelven en la respuesta para que el coordinador decida qué hacer. Los turnos calculados no se listan: se recalculan solos.
10. **Cierre de un horario:** `POST /horarios/{id}/cierre {desde}`, ruta nueva que se suma al CLAUDE.md. Pone `vigente_hasta = desde` en la versión que rige ese día. Si hay una versión posterior, la rechaza con 409 `VERSION_POSTERIOR_EXISTENTE`: el horario se reabriría solo.
11. **Titular válido:** un usuario MEDICO en estado ACTIVO; si no, 422 `TITULAR_INVALIDO`. El alta de un horario exige titular, porque un horario sin titular se muestra como BAJA (D24) y eso solo tiene sentido después de una baja o de un cambio explícito. No se valida que dos horarios del mismo médico se superpongan: D10 no lo pide y con frecuencias distintas es un cálculo aparte (queda anotado como posible mejora).
12. **Activar solo de PENDIENTE a ACTIVO.** `PATCH /usuarios/{id}` acepta `estado: "ACTIVO"` y/o `rol`. No pasa a BAJA (para eso está su propia ruta) ni vuelve a PENDIENTE. Una baja no se reactiva en F5.
13. **`POST /usuarios` no se implementa.** Las altas son por registro con Supabase Auth (D30); se quita del CLAUDE.md en la tarea 10.
14. **Sin bitácora ni notificaciones en F5.** D22 excluye los cambios de plantilla, y activar, cambiar el rol o dar de baja no son acciones sobre un turno. La excepción son las vacantes de la tarea 11: las crea la función de Mariano, con su evento y sus notificaciones.
15. **Estado del horario calculado** (`CON_TITULAR`, `SIN_TITULAR`, `CERRADO`), según la versión que rige hoy o, si todavía no empezó, la próxima. La interfaz muestra BAJA para `SIN_TITULAR` (D24). No es una columna (mismo criterio que el semáforo, D08).
16. **Para coordinar con Mariano (sin código en F5):** con la decisión 2, una cuenta BAJA puede entrar hasta su fecha de baja. La elegibilidad de candidatos y postulaciones (F2b, F3) tiene que exigir rol MEDICO y no aceptar a un médico BAJA para turnos posteriores a su fecha de baja.

## Foco de revisión

Casos que las decisiones implican y que es más probable que fallen en uso real. Cada uno tiene su prueba en la tarea indicada.

1. **Baja con fecha futura:** hasta la fecha de baja inclusive, el médico sigue entrando y sus guardias siguen a su nombre; desde el día siguiente salen sin titular. Tarea 1, `test_baja_programada_sigue_entrando_hasta_su_fecha_inclusive`; tarea 8, `test_baja_futura_conserva_las_guardias_hasta_esa_fecha`.
2. **Dos coordinadores que se quitan el rol entre sí a la vez:** uno tiene que fallar con `ULTIMO_COORDINADOR`; nunca puede quedar el servicio sin coordinador. Tarea 9, `test_dos_coordinadores_no_pueden_quitarse_el_rol_a_la_vez`.
3. **Turno ya guardado de un horario que cambia:** conserva su hora y su titular, y aparece en `turnosAfectados`; uno consolidado hoy no aparece. Tarea 5, `test_turnos_ya_guardados_conservan_su_foto_y_se_informan` y `test_turno_consolidado_hoy_no_es_afectado`.
4. **Baja del titular de un horario con renegociación programada:** el tramo hasta la renegociación queda sin titular y la versión programada no se toca. Tarea 8, `test_baja_respeta_una_version_futura_de_otro_medico`.
5. **Dos coordinadores que modifican el mismo horario desde la misma fecha a la vez:** uno espera el bloqueo y falla con 409; no quedan dos versiones superpuestas ni un 500. Tarea 5, `test_dos_cambios_simultaneos_desde_la_misma_fecha`.

---

## Estructura de archivos

```
backend/
  migrations/versions/0003_baja_con_fecha.py       (T1)
  app/modelos/usuario.py                           (T1)  + ck_usuario_fecha_baja
  app/reloj.py                                     (T1)  hoy(reloj)
  app/auth.py                                      (T1)  usuario_actual respeta la baja programada
  app/dominio/plantilla.py                         (T2)  Vigencia, EstadoHorario, lunes_de, validar_fecha_ancla,
                                                         validar_desde, version_que_cubre, hay_version_posterior,
                                                         estado_horario
  app/repos/usuarios.py                            (T3, T4, T9)  listar_usuarios, bloquear_usuario,
                                                         bloquear_con_coordinadores
  app/repos/horarios.py                            (T3, T5, T8)  listar_horarios, obtener_horario, a_vigencia,
                                                         versiones_no_terminadas_por_medico, datos_de,
                                                         bloquear_horario, nueva_version (parte en medio),
                                                         TurnoAfectado, turnos_afectados, versiones_del_medico_desde
  app/servicios/__init__.py                        (T4)
  app/servicios/plantilla.py                       (T4, T5, T6, T8)  validar_titular, crear_horario_pactado,
                                                         abrir_version, cerrar_horario, dejar_sin_titular
  app/servicios/usuarios.py                        (T7, T8, T9, T11)  ResultadoCambio, activar, dar_de_baja,
                                                         cambiar_rol
  app/api/horarios.py                              (T3, T4, T5, T6)
  app/api/usuarios.py                              (T3, T7, T8, T9, T11)
  app/main.py                                      (T3)
  tests/fabricas.py                                (T1, T3, T5)  crear_usuario(fecha_baja), HOY, ZONA,
                                                         crear_horario_de_prueba, guardar_turno, bloqueado_hasta_commit
  tests/conftest.py                                (T3)  fixture como_coordinador
  tests/test_modelo.py, test_reloj.py, test_api_sesion.py          (T1)
  tests/test_plantilla.py                          (T2)
  tests/test_api_staff_listados.py                 (T3)
  tests/test_api_horarios_alta.py                  (T4)
  tests/test_repo_horarios.py                      (T5)
  tests/test_api_horarios_versiones.py             (T5)
  tests/test_concurrencia_staff.py                 (T5, T9)
  tests/test_api_horarios_cierre.py                (T6)
  tests/test_api_usuarios_activacion.py            (T7)
  tests/test_api_usuarios_baja.py                  (T8)
  tests/test_api_usuarios_rol.py                   (T9)
  tests/test_baja_reabre_coberturas.py             (T11)
  CLAUDE.md                                        (T10)
CLAUDE.md, docs/decisiones-arquitectura.md, docs/prompts-principales.md   (T10)
```

---

### Tarea 1: baja programada en el modelo y en los permisos

**Archivos:**
- Crear: `backend/migrations/versions/0003_baja_con_fecha.py`
- Modificar: `backend/app/modelos/usuario.py`, `backend/app/reloj.py`, `backend/app/auth.py`
- Modificar: `backend/tests/fabricas.py`, `backend/tests/test_modelo.py`, `backend/tests/test_reloj.py`, `backend/tests/test_api_sesion.py`

**Interfaces:**
- Consume: `Usuario`, `EstadoUsuario` (F1); `usuario_registrado`, `usuario_actual` (F2); `Reloj`, `RelojFijo`, `get_reloj` (F0).
- Produce: `app.reloj.hoy(reloj: Reloj) -> date`. `crear_usuario(..., fecha_baja: date | None = None)`: si `estado` es BAJA y no se pasa fecha, usa `date(2000, 1, 1)`. Restricción `ck_usuario_fecha_baja`.

- [ ] **Paso 1: fábrica con fecha de baja**

En `backend/tests/fabricas.py`, cambiar `crear_usuario` (agregar `from datetime import date, timedelta` a los imports):

```python
def crear_usuario(
    sesion: Session,
    nombre: str,
    rol: RolUsuario = RolUsuario.MEDICO,
    estado: EstadoUsuario = EstadoUsuario.ACTIVO,
    email: str | None = None,
    con_cuenta: bool = True,
    fecha_baja: date | None = None,
) -> Usuario:
    if estado == EstadoUsuario.BAJA and fecha_baja is None:
        fecha_baja = date(2000, 1, 1)  # baja vieja: ya no entra con ningún reloj
    usuario = Usuario(
        nombre=nombre,
        email=email or f"usuario{next(_secuencia)}@prueba.test",
        rol=rol,
        estado=estado,
        fecha_baja=fecha_baja,
        auth_id=uuid.uuid4() if con_cuenta else None,
    )
    sesion.add(usuario)
    sesion.flush()
    return usuario
```

- [ ] **Paso 2: escribir las pruebas que fallan**

Al final de `backend/tests/test_modelo.py` (sumar `EstadoUsuario` y `RolUsuario` al import de `app.modelos` si faltan, y `from datetime import date`):

```python
def test_baja_sin_fecha_es_rechazada(sesion):
    usuario = Usuario(nombre="Sin fecha", email="sinfecha@prueba.test", rol=RolUsuario.MEDICO, estado=EstadoUsuario.BAJA)
    debe_fallar(sesion, usuario, "ck_usuario_fecha_baja")


def test_fecha_de_baja_en_cuenta_activa_es_rechazada(sesion):
    usuario = Usuario(
        nombre="Activo", email="activo@prueba.test", rol=RolUsuario.MEDICO,
        estado=EstadoUsuario.ACTIVO, fecha_baja=date(2026, 10, 20),
    )
    debe_fallar(sesion, usuario, "ck_usuario_fecha_baja")
```

Al final de `backend/tests/test_reloj.py` (sumar `from datetime import UTC, date, datetime` y `from app.reloj import RelojFijo, hoy` si faltan):

```python
def test_hoy_usa_la_zona_del_servicio():
    # 01:30 UTC del 13/10 son las 22:30 del 12/10 en Buenos Aires.
    assert hoy(RelojFijo(datetime(2026, 10, 13, 1, 30, tzinfo=UTC))) == date(2026, 10, 12)
```

Al final de `backend/tests/test_api_sesion.py` (sumar `from datetime import date` si falta):

```python
def test_baja_programada_sigue_entrando_hasta_su_fecha_inclusive(cliente, sesion, reloj):
    # reloj: lunes 12/10/2026 09:00. D24: activo hasta la fecha de baja inclusive.
    medico = crear_usuario(sesion, "Se va hoy", estado=EstadoUsuario.BAJA, fecha_baja=date(2026, 10, 12))
    r = cliente.get("/api/turnos", params={"desde": "2026-10-12", "hasta": "2026-10-12"}, headers=encabezados(medico))
    assert r.status_code == 200


def test_baja_cumplida_ya_no_entra(cliente, sesion, reloj):
    medico = crear_usuario(sesion, "Se fue ayer", estado=EstadoUsuario.BAJA, fecha_baja=date(2026, 10, 11))
    r = cliente.get("/api/turnos", params={"desde": "2026-10-12", "hasta": "2026-10-12"}, headers=encabezados(medico))
    assert r.status_code == 403
    assert r.json()["codigo"] == "CUENTA_DADA_DE_BAJA"
```

- [ ] **Paso 3: correr y verificar que fallan**

Run: `.venv/bin/pytest tests/test_modelo.py tests/test_reloj.py tests/test_api_sesion.py -q`
Expected: FAIL. Las dos del modelo no encuentran la restricción, `hoy` no existe y la baja programada recibe 403.

- [ ] **Paso 4: migración 0003**

Crear `backend/migrations/versions/0003_baja_con_fecha.py`:

```python
"""Estado BAJA y fecha de baja siempre juntos (D24)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-07
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_UPGRADE = [
    # D24: toda baja tiene fecha (último día activo) y solo una cuenta dada de baja la tiene.
    "ALTER TABLE usuario ADD CONSTRAINT ck_usuario_fecha_baja CHECK ((estado = 'BAJA') = (fecha_baja IS NOT NULL))",
]

_DOWNGRADE = [
    "ALTER TABLE usuario DROP CONSTRAINT ck_usuario_fecha_baja",
]


def upgrade() -> None:
    for sentencia in _UPGRADE:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _DOWNGRADE:
        op.execute(sentencia)
```

En `backend/app/modelos/usuario.py`, sumar `CheckConstraint` al import de `sqlalchemy` y, dentro de `Usuario`, debajo de `__tablename__`:

```python
    __table_args__ = (
        CheckConstraint("(estado = 'BAJA') = (fecha_baja IS NOT NULL)", name="ck_usuario_fecha_baja"),
    )
```

- [ ] **Paso 5: `hoy(reloj)`**

En `backend/app/reloj.py`, cambiar el import a `from datetime import date, datetime, timedelta` y agregar al final:

```python
def hoy(reloj: Reloj) -> date:
    """Fecha de "ahora" en la zona del servicio (D13). Toda regla que compare con hoy usa esta función."""
    return reloj.ahora().astimezone(get_settings().zona).date()
```

- [ ] **Paso 6: `usuario_actual` respeta la baja programada**

En `backend/app/auth.py`, agregar `from app.reloj import Reloj, get_reloj, hoy` y reemplazar `usuario_actual`:

```python
def usuario_actual(usuario: Usuario = Depends(usuario_registrado), reloj: Reloj = Depends(get_reloj)) -> Usuario:
    """Usuario con acceso (D23, D30). Lo exige todo endpoint salvo /health, /me y /registro.

    Una baja (D24) deja entrar hasta la fecha de baja inclusive: el estado pasa a BAJA al registrarla,
    pero el médico todavía trabaja hasta ese día.
    """
    if usuario.estado == EstadoUsuario.PENDIENTE:
        raise ErrorDominio("CUENTA_PENDIENTE", "Un coordinador tiene que activar tu cuenta.", 403)
    if usuario.estado == EstadoUsuario.BAJA and usuario.fecha_baja < hoy(reloj):
        raise ErrorDominio("CUENTA_DADA_DE_BAJA", "La cuenta está dada de baja.", 403)
    return usuario
```

Actualizar el docstring del módulo: donde dice "usuario_actual (Usuario ACTIVO)", poner "usuario_actual (Usuario ACTIVO, o BAJA hasta su fecha de baja inclusive)".

- [ ] **Paso 7: correr toda la suite**

Run: `.venv/bin/pytest -q`
Expected: todo pasa. Las pruebas de F2 que crean cuentas BAJA reciben `fecha_baja = 2000-01-01` y siguen recibiendo `CUENTA_DADA_DE_BAJA`. `test_sin_hora_del_sistema` sigue pasando: `hoy` usa el reloj.

- [ ] **Paso 8: commit**

```bash
git add backend/migrations/versions/0003_baja_con_fecha.py backend/app/modelos/usuario.py backend/app/reloj.py backend/app/auth.py backend/tests/fabricas.py backend/tests/test_modelo.py backend/tests/test_reloj.py backend/tests/test_api_sesion.py
git commit -m "$(cat <<'EOF'
Baja programada: fecha de baja obligatoria y acceso hasta ese día inclusive (D24)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarea 2: reglas puras de la plantilla

**Archivos:**
- Crear: `backend/app/dominio/plantilla.py`
- Crear: `backend/tests/test_plantilla.py`

**Interfaces:**
- Consume: `ErrorDominio` (F0).
- Produce (en `app.dominio.plantilla`):
  - `Vigencia(version_id: int, medico_id: int | None, vigente_desde: date, vigente_hasta: date | None)`, dataclass inmutable con `rige(fecha: date) -> bool`.
  - `EstadoHorario` (enum str): `CON_TITULAR`, `SIN_TITULAR`, `CERRADO`.
  - `lunes_de(fecha: date) -> date`
  - `validar_fecha_ancla(fecha_ancla: date) -> None`: 422 `FECHA_ANCLA_NO_LUNES`.
  - `validar_desde(desde: date, hoy: date) -> None`: 422 `FECHA_PASADA`.
  - `version_que_cubre(vigencias: Sequence[Vigencia], desde: date, horario_id: int) -> Vigencia`: 409 `HORARIO_SIN_VIGENCIA` o 409 `VERSION_EN_ESA_FECHA`.
  - `hay_version_posterior(vigencias: Sequence[Vigencia], desde: date) -> bool`
  - `estado_horario(vigencias: Sequence[Vigencia], hoy: date) -> EstadoHorario`

- [ ] **Paso 1: escribir las pruebas que fallan**

Crear `backend/tests/test_plantilla.py`:

```python
from datetime import date

import pytest

from app.dominio.plantilla import (
    EstadoHorario,
    Vigencia,
    estado_horario,
    hay_version_posterior,
    lunes_de,
    validar_desde,
    validar_fecha_ancla,
    version_que_cubre,
)
from app.errores import ErrorDominio

HOY = date(2026, 10, 12)


def v(version_id, desde, hasta=None, medico_id=1) -> Vigencia:
    return Vigencia(version_id=version_id, medico_id=medico_id, vigente_desde=desde, vigente_hasta=hasta)


def error_de(funcion, *args) -> tuple[str, int]:
    with pytest.raises(ErrorDominio) as excinfo:
        funcion(*args)
    return excinfo.value.codigo, excinfo.value.status


def test_lunes_de():
    assert lunes_de(date(2026, 10, 18)) == date(2026, 10, 12)  # domingo
    assert lunes_de(date(2026, 10, 12)) == date(2026, 10, 12)


def test_fecha_ancla_tiene_que_ser_lunes():
    validar_fecha_ancla(date(2026, 10, 12))
    assert error_de(validar_fecha_ancla, date(2026, 10, 13)) == ("FECHA_ANCLA_NO_LUNES", 422)


def test_desde_hoy_se_acepta_y_ayer_no():
    validar_desde(HOY, HOY)
    assert error_de(validar_desde, date(2026, 10, 11), HOY) == ("FECHA_PASADA", 422)


def test_version_que_cubre_devuelve_la_que_rige_ese_dia():
    versiones = [v(1, date(2026, 9, 7), date(2026, 11, 2)), v(2, date(2026, 11, 2))]
    assert version_que_cubre(versiones, date(2026, 10, 20), 7).version_id == 1
    assert version_que_cubre(versiones, date(2026, 11, 9), 7).version_id == 2


def test_version_que_empieza_ese_dia_no_se_parte():
    versiones = [v(1, date(2026, 9, 7), date(2026, 11, 2)), v(2, date(2026, 11, 2))]
    assert error_de(version_que_cubre, versiones, date(2026, 11, 2), 7) == ("VERSION_EN_ESA_FECHA", 409)


@pytest.mark.parametrize("desde", [date(2026, 10, 20), date(2026, 11, 2)])
def test_horario_cerrado_no_tiene_version_que_partir(desde):
    versiones = [v(1, date(2026, 9, 7), date(2026, 10, 20))]
    assert error_de(version_que_cubre, versiones, desde, 7) == ("HORARIO_SIN_VIGENCIA", 409)


def test_horario_que_todavia_no_empezo_no_tiene_version_que_partir():
    versiones = [v(1, date(2026, 11, 2))]
    assert error_de(version_que_cubre, versiones, date(2026, 10, 20), 7) == ("HORARIO_SIN_VIGENCIA", 409)


def test_hay_version_posterior():
    versiones = [v(1, date(2026, 9, 7), date(2026, 11, 2)), v(2, date(2026, 11, 2))]
    assert hay_version_posterior(versiones, date(2026, 10, 20))
    assert not hay_version_posterior(versiones, date(2026, 11, 9))


@pytest.mark.parametrize(
    "versiones,esperado",
    [
        ([v(1, date(2026, 9, 7))], EstadoHorario.CON_TITULAR),
        # La baja rige desde mañana: hoy todavía tiene titular.
        ([v(1, date(2026, 9, 7), date(2026, 10, 13)), v(2, date(2026, 10, 13), medico_id=None)], EstadoHorario.CON_TITULAR),
        ([v(1, date(2026, 9, 7), HOY), v(2, HOY, medico_id=None)], EstadoHorario.SIN_TITULAR),
        ([v(1, date(2026, 9, 7), HOY)], EstadoHorario.CERRADO),
        # Todavía no empezó: cuenta la próxima versión.
        ([v(1, date(2026, 11, 2))], EstadoHorario.CON_TITULAR),
        ([v(1, date(2026, 11, 2), medico_id=None)], EstadoHorario.SIN_TITULAR),
    ],
)
def test_estado_horario(versiones, esperado):
    assert estado_horario(versiones, HOY) == esperado
```

- [ ] **Paso 2: correr y verificar que fallan**

Run: `.venv/bin/pytest tests/test_plantilla.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.dominio.plantilla'`.

- [ ] **Paso 3: implementar**

Crear `backend/app/dominio/plantilla.py`:

```python
"""Reglas de la plantilla de horarios pactados (D10, D12, D14, D24). Lógica pura: sin base de datos ni FastAPI."""

import enum
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from app.errores import ErrorDominio


@dataclass(frozen=True)
class Vigencia:
    """Lo que las reglas necesitan de una versión: su titular y su vigencia [desde, hasta)."""

    version_id: int
    medico_id: int | None
    vigente_desde: date
    vigente_hasta: date | None

    def rige(self, fecha: date) -> bool:
        return self.vigente_desde <= fecha and (self.vigente_hasta is None or fecha < self.vigente_hasta)


class EstadoHorario(str, enum.Enum):
    CON_TITULAR = "CON_TITULAR"
    SIN_TITULAR = "SIN_TITULAR"  # la interfaz lo muestra con la etiqueta BAJA (D24)
    CERRADO = "CERRADO"


def lunes_de(fecha: date) -> date:
    return fecha - timedelta(days=fecha.weekday())


def validar_fecha_ancla(fecha_ancla: date) -> None:
    if fecha_ancla.isoweekday() != 1:
        raise ErrorDominio("FECHA_ANCLA_NO_LUNES", "La fecha ancla tiene que ser un lunes (D14).")


def validar_desde(desde: date, hoy: date) -> None:
    """Un cambio de plantilla nunca empieza en el pasado: reescribiría turnos que ya ocurrieron (D12)."""
    if desde < hoy:
        raise ErrorDominio("FECHA_PASADA", f"El cambio no puede empezar antes de hoy ({hoy:%d/%m/%Y}).")


def version_que_cubre(vigencias: Sequence[Vigencia], desde: date, horario_id: int) -> Vigencia:
    """Versión que se parte en `desde` para abrir otra (D10). La nueva hereda su fin de vigencia."""
    cubre = next((v for v in vigencias if v.rige(desde)), None)
    if cubre is None:
        raise ErrorDominio(
            "HORARIO_SIN_VIGENCIA",
            f"El horario {horario_id} no rige el {desde:%d/%m/%Y}: está cerrado o todavía no empezó.",
            409,
        )
    if cubre.vigente_desde == desde:
        raise ErrorDominio(
            "VERSION_EN_ESA_FECHA", f"El horario {horario_id} ya tiene una versión que empieza el {desde:%d/%m/%Y}.", 409
        )
    return cubre


def hay_version_posterior(vigencias: Sequence[Vigencia], desde: date) -> bool:
    return any(v.vigente_desde > desde for v in vigencias)


def estado_horario(vigencias: Sequence[Vigencia], hoy: date) -> EstadoHorario:
    """Se calcula, no se guarda (D08): según la versión que rige hoy o, si todavía no empezó, la próxima."""
    referencia = next((v for v in vigencias if v.rige(hoy)), None)
    if referencia is None:
        futuras = sorted((v for v in vigencias if v.vigente_desde > hoy), key=lambda v: v.vigente_desde)
        referencia = futuras[0] if futuras else None
    if referencia is None:
        return EstadoHorario.CERRADO
    return EstadoHorario.SIN_TITULAR if referencia.medico_id is None else EstadoHorario.CON_TITULAR
```

- [ ] **Paso 4: correr y verificar que pasan**

Run: `.venv/bin/pytest tests/test_plantilla.py -q`
Expected: PASS.

- [ ] **Paso 5: commit**

```bash
git add backend/app/dominio/plantilla.py backend/tests/test_plantilla.py
git commit -m "$(cat <<'EOF'
Reglas puras de la plantilla: versión que se parte, fecha ancla y estado del horario (D10, D12, D14)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarea 3: GET /api/usuarios y GET /api/horarios

**Archivos:**
- Crear: `backend/app/api/horarios.py`, `backend/app/api/usuarios.py`
- Modificar: `backend/app/main.py`, `backend/app/repos/horarios.py`, `backend/app/repos/usuarios.py`
- Modificar: `backend/tests/fabricas.py`, `backend/tests/conftest.py`
- Crear: `backend/tests/test_api_staff_listados.py`

**Interfaces:**
- Consume: `requiere_coordinador` (F2), `hoy`, `get_reloj` (T1), `Vigencia`, `EstadoHorario`, `estado_horario` (T2), `crear_horario`, `DatosVersion` (F1).
- Produce:
  - `app.repos.usuarios.listar_usuarios(sesion) -> list[Usuario]`, ordenados por nombre e id.
  - `app.repos.horarios.listar_horarios(sesion) -> list[HorarioPactado]` y `obtener_horario(sesion, horario_id: int) -> HorarioPactado | None`, ambos con versiones y médicos cargados y releídos de la base.
  - `app.repos.horarios.a_vigencia(version: VersionHorario) -> Vigencia`
  - `app.repos.horarios.versiones_no_terminadas_por_medico(sesion, hoy: date, medico_id: int | None = None) -> dict[int, list[VersionHorario]]`
  - `app.api.horarios`: `PersonaOut`, `VersionOut`, `HorarioOut`, `persona_out`, `version_out`, `horario_out(horario, dia) -> HorarioOut`.
  - `app.api.usuarios`: `HorarioDelMedicoOut`, `UsuarioStaffOut`, `usuario_out(usuario, versiones) -> UsuarioStaffOut`.
  - Fábricas: `HOY = date(2026, 10, 12)`, `ZONA`, `crear_horario_de_prueba(sesion, medico_id, dia=2, hora=time(8), dur=12, frec=1, ancla=date(2026, 9, 7), desde=date(2026, 9, 7), hasta=None) -> HorarioPactado`.
  - Fixture `como_coordinador(cliente, sesion, reloj) -> Usuario`: crea a Enzo, coordinador activo, y deja su token en el cliente.

- [ ] **Paso 1: fábricas y fixture**

En `backend/tests/fabricas.py`, sumar a los imports `from datetime import date, time, timedelta`, `from zoneinfo import ZoneInfo`, `from app.modelos import EstadoUsuario, HorarioPactado, RolUsuario, Usuario` y `from app.repos.horarios import DatosVersion, crear_horario`, y agregar:

```python
ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
HOY = date(2026, 10, 12)  # fecha del RelojFijo de conftest (lunes 12/10/2026 09:00)


def crear_horario_de_prueba(
    sesion: Session,
    medico_id: int | None,
    dia: int = 2,
    hora: time = time(8),
    dur: int = 12,
    frec: int = 1,
    ancla: date = date(2026, 9, 7),
    desde: date = date(2026, 9, 7),
    hasta: date | None = None,
) -> HorarioPactado:
    """Por defecto: martes de 08:00 a 20:00 todas las semanas, vigente desde el 7/9."""
    datos = DatosVersion(
        medico_id=medico_id,
        dia_semana=dia,
        hora_inicio=hora,
        duracion_horas=dur,
        frecuencia_semanas=frec,
        fecha_ancla=ancla,
    )
    return crear_horario(sesion, datos, desde, hasta)
```

En `backend/tests/conftest.py`, sumar `from app.modelos import RolUsuario` y `from fabricas import SECRETO_PRUEBA, crear_usuario, encabezados` (reemplazando el import actual de fabricas), y agregar al final:

```python
@pytest.fixture
def como_coordinador(cliente, sesion, reloj):
    """Enzo, coordinador activo, con su token en el cliente y el reloj fijo en el lunes 12/10/2026."""
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    cliente.headers.update(encabezados(enzo))
    return enzo
```

- [ ] **Paso 2: escribir las pruebas que fallan**

Crear `backend/tests/test_api_staff_listados.py`:

```python
from datetime import date

import pytest

from app.modelos import EstadoUsuario, RolUsuario
from fabricas import crear_horario_de_prueba, crear_usuario, encabezados


def test_lista_de_usuarios_formato_exacto(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones", email="carlos@prueba.test")
    vigente = crear_horario_de_prueba(sesion, carlos.id)
    crear_horario_de_prueba(sesion, carlos.id, dia=5, hasta=date(2026, 10, 1))  # terminado: no se lista

    r = cliente.get("/api/usuarios")

    assert r.status_code == 200
    [carlos_out] = [u for u in r.json() if u["id"] == carlos.id]
    assert carlos_out == {
        "id": carlos.id,
        "nombre": "Carlos Lugones",
        "email": "carlos@prueba.test",
        "rol": "MEDICO",
        "estado": "ACTIVO",
        "fechaBaja": None,
        "horarios": [
            {
                "horarioId": vigente.id,
                "diaSemana": 2,
                "horaInicio": "08:00:00",
                "duracionHoras": 12,
                "frecuenciaSemanas": 1,
                "fechaAncla": "2026-09-07",
                "vigenteDesde": "2026-09-07",
                "vigenteHasta": None,
            }
        ],
    }


def test_lista_de_usuarios_incluye_pendientes_bajas_y_coordinadores_ordenados_por_nombre(cliente, sesion, como_coordinador):
    crear_usuario(sesion, "Zoe Pendiente", estado=EstadoUsuario.PENDIENTE)
    crear_usuario(sesion, "Ana Baja", estado=EstadoUsuario.BAJA, fecha_baja=date(2026, 10, 1))

    usuarios = cliente.get("/api/usuarios").json()

    assert [u["nombre"] for u in usuarios] == ["Ana Baja", "Enzo", "Zoe Pendiente"]
    assert usuarios[0]["fechaBaja"] == "2026-10-01"
    assert usuarios[1]["rol"] == "COORDINADOR"
    assert usuarios[2]["estado"] == "PENDIENTE"


def test_lista_de_horarios_con_estado_calculado(cliente, sesion, como_coordinador):
    paula = crear_usuario(sesion, "Paula Méndez")
    con_titular = crear_horario_de_prueba(sesion, paula.id)
    sin_titular = crear_horario_de_prueba(sesion, None)
    cerrado = crear_horario_de_prueba(sesion, paula.id, hasta=date(2026, 10, 1))

    r = cliente.get("/api/horarios")

    assert r.status_code == 200
    por_id = {h["id"]: h for h in r.json()}
    assert por_id[con_titular.id]["estado"] == "CON_TITULAR"
    assert por_id[sin_titular.id]["estado"] == "SIN_TITULAR"
    assert por_id[cerrado.id]["estado"] == "CERRADO"
    assert por_id[con_titular.id]["versiones"] == [
        {
            "id": por_id[con_titular.id]["versiones"][0]["id"],
            "medico": {"id": paula.id, "nombre": "Paula Méndez"},
            "diaSemana": 2,
            "horaInicio": "08:00:00",
            "duracionHoras": 12,
            "frecuenciaSemanas": 1,
            "fechaAncla": "2026-09-07",
            "vigenteDesde": "2026-09-07",
            "vigenteHasta": None,
        }
    ]
    assert por_id[sin_titular.id]["versiones"][0]["medico"] is None


@pytest.mark.parametrize("ruta", ["/api/usuarios", "/api/horarios"])
def test_un_medico_no_ve_el_staff(cliente, sesion, reloj, ruta):
    medico = crear_usuario(sesion, "Carlos Lugones")
    r = cliente.get(ruta, headers=encabezados(medico))
    assert r.status_code == 403
    assert r.json()["codigo"] == "SIN_PERMISO"
```

- [ ] **Paso 3: correr y verificar que fallan**

Run: `.venv/bin/pytest tests/test_api_staff_listados.py -q`
Expected: FAIL con 404 (las rutas no existen).

- [ ] **Paso 4: repos**

En `backend/app/repos/usuarios.py`, agregar:

```python
def listar_usuarios(sesion: Session) -> list[Usuario]:
    """Todos, en cualquier estado: nunca se borra un usuario (D24)."""
    return list(sesion.scalars(select(Usuario).order_by(Usuario.nombre, Usuario.id)))
```

En `backend/app/repos/horarios.py`, sumar a los imports `from collections import defaultdict`, `from sqlalchemy import func, or_, select`, `from sqlalchemy.orm import Session, selectinload` y `from app.dominio.plantilla import Vigencia`, y agregar:

```python
def _con_versiones():
    return (
        select(HorarioPactado)
        .options(selectinload(HorarioPactado.versiones).selectinload(VersionHorario.medico))
        .execution_options(populate_existing=True)
    )


def listar_horarios(sesion: Session) -> list[HorarioPactado]:
    """Todos los horarios, también los cerrados, con sus versiones ordenadas por vigencia."""
    return list(sesion.scalars(_con_versiones().order_by(HorarioPactado.id)))


def obtener_horario(sesion: Session, horario_id: int) -> HorarioPactado | None:
    return sesion.scalar(_con_versiones().where(HorarioPactado.id == horario_id))


def a_vigencia(version: VersionHorario) -> Vigencia:
    return Vigencia(
        version_id=version.id,
        medico_id=version.medico_id,
        vigente_desde=version.vigente_desde,
        vigente_hasta=version.vigente_hasta,
    )


def versiones_no_terminadas_por_medico(
    sesion: Session, hoy: date, medico_id: int | None = None
) -> dict[int, list[VersionHorario]]:
    """Versiones con titular que rigen hoy o empiezan después, agrupadas por médico."""
    consulta = (
        select(VersionHorario)
        .where(
            VersionHorario.medico_id.is_not(None),
            or_(VersionHorario.vigente_hasta.is_(None), VersionHorario.vigente_hasta > hoy),
        )
        .order_by(VersionHorario.vigente_desde, VersionHorario.horario_id)
    )
    if medico_id is not None:
        consulta = consulta.where(VersionHorario.medico_id == medico_id)
    por_medico: dict[int, list[VersionHorario]] = defaultdict(list)
    for version in sesion.scalars(consulta):
        por_medico[version.medico_id].append(version)
    return por_medico
```

- [ ] **Paso 5: routers**

Crear `backend/app/api/horarios.py`:

```python
from datetime import date, datetime, time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.esquemas import Esquema
from app.auth import requiere_coordinador
from app.db import get_db
from app.dominio.calendario import Titular
from app.dominio.plantilla import EstadoHorario, estado_horario
from app.modelos import HorarioPactado, Usuario, VersionHorario
from app.reloj import Reloj, get_reloj, hoy
from app.repos.horarios import a_vigencia, listar_horarios

router = APIRouter()


class PersonaOut(Esquema):
    id: int
    nombre: str


class VersionOut(Esquema):
    id: int
    medico: PersonaOut | None
    dia_semana: int
    hora_inicio: time
    duracion_horas: int
    frecuencia_semanas: int
    fecha_ancla: date
    vigente_desde: date
    vigente_hasta: date | None


class HorarioOut(Esquema):
    id: int
    estado: EstadoHorario
    versiones: list[VersionOut]


def persona_out(persona: Usuario | Titular | None) -> PersonaOut | None:
    return PersonaOut(id=persona.id, nombre=persona.nombre) if persona is not None else None


def version_out(version: VersionHorario) -> VersionOut:
    return VersionOut(
        id=version.id,
        medico=persona_out(version.medico),
        dia_semana=version.dia_semana,
        hora_inicio=version.hora_inicio,
        duracion_horas=version.duracion_horas,
        frecuencia_semanas=version.frecuencia_semanas,
        fecha_ancla=version.fecha_ancla,
        vigente_desde=version.vigente_desde,
        vigente_hasta=version.vigente_hasta,
    )


def horario_out(horario: HorarioPactado, dia: date) -> HorarioOut:
    return HorarioOut(
        id=horario.id,
        estado=estado_horario([a_vigencia(v) for v in horario.versiones], dia),
        versiones=[version_out(v) for v in horario.versiones],
    )


@router.get("/horarios", response_model=list[HorarioOut])
def listar(
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> list[HorarioOut]:
    """Plantilla completa con su historia de versiones (D10) y el estado calculado para hoy (D24)."""
    dia = hoy(reloj)
    return [horario_out(h, dia) for h in listar_horarios(db)]
```

Crear `backend/app/api/usuarios.py`:

```python
from datetime import date, time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.esquemas import Esquema
from app.auth import requiere_coordinador
from app.db import get_db
from app.modelos import EstadoUsuario, RolUsuario, Usuario, VersionHorario
from app.reloj import Reloj, get_reloj, hoy
from app.repos.horarios import versiones_no_terminadas_por_medico
from app.repos.usuarios import listar_usuarios

router = APIRouter()


class HorarioDelMedicoOut(Esquema):
    horario_id: int
    dia_semana: int
    hora_inicio: time
    duracion_horas: int
    frecuencia_semanas: int
    fecha_ancla: date
    vigente_desde: date
    vigente_hasta: date | None


class UsuarioStaffOut(Esquema):
    id: int
    nombre: str
    email: str
    rol: RolUsuario
    estado: EstadoUsuario
    fecha_baja: date | None
    horarios: list[HorarioDelMedicoOut]


def _horario_del_medico(version: VersionHorario) -> HorarioDelMedicoOut:
    return HorarioDelMedicoOut(
        horario_id=version.horario_id,
        dia_semana=version.dia_semana,
        hora_inicio=version.hora_inicio,
        duracion_horas=version.duracion_horas,
        frecuencia_semanas=version.frecuencia_semanas,
        fecha_ancla=version.fecha_ancla,
        vigente_desde=version.vigente_desde,
        vigente_hasta=version.vigente_hasta,
    )


def usuario_out(usuario: Usuario, versiones: list[VersionHorario]) -> UsuarioStaffOut:
    return UsuarioStaffOut(
        id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
        rol=usuario.rol,
        estado=usuario.estado,
        fecha_baja=usuario.fecha_baja,
        horarios=[_horario_del_medico(v) for v in versiones],
    )


@router.get("/usuarios", response_model=list[UsuarioStaffOut])
def listar(
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> list[UsuarioStaffOut]:
    """Staff con rol, estado y horarios que rigen hoy o empiezan después (D26)."""
    por_medico = versiones_no_terminadas_por_medico(db, hoy(reloj))
    return [usuario_out(u, por_medico.get(u.id, [])) for u in listar_usuarios(db)]
```

En `backend/app/main.py`, cambiar el import a `from app.api import health, horarios, sesion, turnos, usuarios` y agregar, después de `api.include_router(turnos.router)`:

```python
    api.include_router(usuarios.router)
    api.include_router(horarios.router)
```

- [ ] **Paso 6: correr y verificar que pasan**

Run: `.venv/bin/pytest tests/test_api_staff_listados.py -q && .venv/bin/pytest -q`
Expected: PASS y toda la suite verde.

- [ ] **Paso 7: commit**

```bash
git add backend/app/api/horarios.py backend/app/api/usuarios.py backend/app/main.py backend/app/repos/horarios.py backend/app/repos/usuarios.py backend/tests/fabricas.py backend/tests/conftest.py backend/tests/test_api_staff_listados.py
git commit -m "$(cat <<'EOF'
GET /api/usuarios y GET /api/horarios para la pantalla de staff (D26)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarea 4: POST /api/horarios (alta de un horario pactado)

**Archivos:**
- Crear: `backend/app/servicios/__init__.py` (vacío), `backend/app/servicios/plantilla.py`
- Modificar: `backend/app/repos/usuarios.py`, `backend/app/api/horarios.py`
- Crear: `backend/tests/test_api_horarios_alta.py`

**Interfaces:**
- Consume: `validar_desde`, `validar_fecha_ancla`, `lunes_de` (T2); `crear_horario`, `DatosVersion` (F1); `obtener_horario`, `horario_out` (T3).
- Produce:
  - `app.repos.usuarios.bloquear_usuario(sesion, usuario_id: int) -> Usuario | None`: `SELECT ... FOR UPDATE`, releído de la base.
  - `app.servicios.plantilla.validar_titular(sesion, medico_id: int) -> Usuario`: bloquea y exige MEDICO ACTIVO; si no, 422 `TITULAR_INVALIDO`.
  - `app.servicios.plantilla.crear_horario_pactado(sesion, datos: DatosVersion, vigente_desde: date, hoy: date) -> HorarioPactado`.

- [ ] **Paso 1: escribir las pruebas que fallan**

Crear `backend/tests/test_api_horarios_alta.py`:

```python
from datetime import date

import pytest

from app.modelos import EstadoUsuario, RolUsuario
from fabricas import crear_usuario, encabezados


def cuerpo(medico_id, **cambios) -> dict:
    base = {
        "medicoId": medico_id,
        "diaSemana": 6,
        "horaInicio": "08:00",
        "duracionHoras": 12,
        "frecuenciaSemanas": 1,
        "fechaAncla": "2026-10-12",
        "vigenteDesde": "2026-10-17",
    }
    base.update(cambios)
    return base


def test_alta_de_horario_formato_exacto_y_aparece_en_el_calendario(cliente, sesion, como_coordinador):
    florencia = crear_usuario(sesion, "Florencia Lucca")

    r = cliente.post("/api/horarios", json=cuerpo(florencia.id))

    assert r.status_code == 201
    datos = r.json()
    assert datos == {
        "id": datos["id"],
        "estado": "CON_TITULAR",
        "versiones": [
            {
                "id": datos["versiones"][0]["id"],
                "medico": {"id": florencia.id, "nombre": "Florencia Lucca"},
                "diaSemana": 6,
                "horaInicio": "08:00:00",
                "duracionHoras": 12,
                "frecuenciaSemanas": 1,
                "fechaAncla": "2026-10-12",
                "vigenteDesde": "2026-10-17",
                "vigenteHasta": None,
            }
        ],
    }
    turnos = cliente.get("/api/turnos", params={"desde": "2026-10-17", "hasta": "2026-10-17"}).json()
    assert [t["id"] for t in turnos] == [f"{datos['id']}:2026-10-17"]


def test_sin_fecha_ancla_usa_el_lunes_de_la_semana_de_inicio(cliente, sesion, como_coordinador):
    florencia = crear_usuario(sesion, "Florencia Lucca")
    datos = cuerpo(florencia.id)
    del datos["fechaAncla"]
    r = cliente.post("/api/horarios", json=datos)
    assert r.status_code == 201
    assert r.json()["versiones"][0]["fechaAncla"] == "2026-10-12"


def test_fecha_ancla_que_no_es_lunes(cliente, sesion, como_coordinador):
    florencia = crear_usuario(sesion, "Florencia Lucca")
    r = cliente.post("/api/horarios", json=cuerpo(florencia.id, fechaAncla="2026-10-13"))
    assert r.status_code == 422
    assert r.json()["codigo"] == "FECHA_ANCLA_NO_LUNES"


def test_alta_con_inicio_en_el_pasado(cliente, sesion, como_coordinador):
    florencia = crear_usuario(sesion, "Florencia Lucca")
    r = cliente.post("/api/horarios", json=cuerpo(florencia.id, vigenteDesde="2026-10-11"))
    assert r.status_code == 422
    assert r.json()["codigo"] == "FECHA_PASADA"


@pytest.mark.parametrize(
    "rol,estado",
    [
        (RolUsuario.COORDINADOR, EstadoUsuario.ACTIVO),
        (RolUsuario.MEDICO, EstadoUsuario.PENDIENTE),
        (RolUsuario.MEDICO, EstadoUsuario.BAJA),
    ],
)
def test_titular_que_no_es_medico_activo(cliente, sesion, como_coordinador, rol, estado):
    otro = crear_usuario(sesion, "No elegible", rol=rol, estado=estado)
    r = cliente.post("/api/horarios", json=cuerpo(otro.id))
    assert r.status_code == 422
    assert r.json()["codigo"] == "TITULAR_INVALIDO"


def test_titular_inexistente(cliente, como_coordinador):
    r = cliente.post("/api/horarios", json=cuerpo(999999))
    assert r.status_code == 422
    assert r.json()["codigo"] == "TITULAR_INVALIDO"


@pytest.mark.parametrize("cambio", [{"duracionHoras": 25}, {"diaSemana": 8}, {"medicoId": None}, {"frecuenciaSemanas": 0}])
def test_datos_fuera_de_rango_son_validacion(cliente, sesion, como_coordinador, cambio):
    florencia = crear_usuario(sesion, "Florencia Lucca")
    r = cliente.post("/api/horarios", json=cuerpo(florencia.id, **cambio))
    assert r.status_code == 422
    assert r.json()["codigo"] == "VALIDACION"


def test_un_medico_no_carga_horarios(cliente, sesion, reloj):
    medico = crear_usuario(sesion, "Carlos Lugones")
    r = cliente.post("/api/horarios", json=cuerpo(medico.id), headers=encabezados(medico))
    assert r.status_code == 403
    assert r.json()["codigo"] == "SIN_PERMISO"
```

- [ ] **Paso 2: correr y verificar que fallan**

Run: `.venv/bin/pytest tests/test_api_horarios_alta.py -q`
Expected: FAIL con 405 (`METODO_NO_PERMITIDO`): la ruta GET existe, pero la POST no.

- [ ] **Paso 3: bloqueo de usuario**

En `backend/app/repos/usuarios.py`, agregar:

```python
def bloquear_usuario(sesion: Session, usuario_id: int) -> Usuario | None:
    """Bloquea la fila hasta el fin de la transacción (regla 8) y la relee de la base."""
    return sesion.scalar(
        select(Usuario)
        .where(Usuario.id == usuario_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
```

- [ ] **Paso 4: servicio**

Crear `backend/app/servicios/__init__.py` vacío y `backend/app/servicios/plantilla.py`:

```python
"""Operaciones sobre la plantilla (D10, D12, D23, D24). Combinan reglas de dominio y repos; no hacen commit.

Orden de bloqueos: primero el usuario, después el horario. La baja y el cambio de rol también lo siguen,
para que dos operaciones simultáneas no se esperen en cruz.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.dominio.plantilla import validar_desde, validar_fecha_ancla
from app.errores import ErrorDominio
from app.modelos import EstadoUsuario, HorarioPactado, RolUsuario, Usuario
from app.repos.horarios import DatosVersion, crear_horario
from app.repos.usuarios import bloquear_usuario


def validar_titular(sesion: Session, medico_id: int) -> Usuario:
    """El titular es un médico activo (D23). Queda bloqueado: una baja o un cambio de rol en paralelo espera."""
    medico = bloquear_usuario(sesion, medico_id)
    if medico is None or medico.rol != RolUsuario.MEDICO or medico.estado != EstadoUsuario.ACTIVO:
        raise ErrorDominio("TITULAR_INVALIDO", "El titular tiene que ser un médico activo (D23).")
    return medico


def crear_horario_pactado(sesion: Session, datos: DatosVersion, vigente_desde: date, hoy: date) -> HorarioPactado:
    validar_desde(vigente_desde, hoy)
    validar_fecha_ancla(datos.fecha_ancla)
    validar_titular(sesion, datos.medico_id)
    return crear_horario(sesion, datos, vigente_desde)
```

- [ ] **Paso 5: endpoint**

En `backend/app/api/horarios.py`, sumar a los imports `from pydantic import Field`, `from app.dominio.plantilla import EstadoHorario, estado_horario, lunes_de`, `from app.repos.horarios import DatosVersion, a_vigencia, listar_horarios, obtener_horario` y `from app.servicios.plantilla import crear_horario_pactado`, y agregar:

```python
class HorarioIn(Esquema):
    medico_id: int
    dia_semana: int = Field(ge=1, le=7)
    hora_inicio: time
    duracion_horas: int = Field(ge=1, le=24)
    frecuencia_semanas: int = Field(default=1, ge=1, le=52)
    fecha_ancla: date | None = None  # vacía: el lunes de la semana de vigenteDesde (D14)
    vigente_desde: date


@router.post("/horarios", response_model=HorarioOut, status_code=201)
def crear(
    datos: HorarioIn,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> HorarioOut:
    """Carga un horario pactado con su primera versión (D10). El titular tiene que ser un médico activo."""
    dia = hoy(reloj)
    version = DatosVersion(
        medico_id=datos.medico_id,
        dia_semana=datos.dia_semana,
        hora_inicio=datos.hora_inicio,
        duracion_horas=datos.duracion_horas,
        frecuencia_semanas=datos.frecuencia_semanas,
        fecha_ancla=datos.fecha_ancla or lunes_de(datos.vigente_desde),
    )
    horario = crear_horario_pactado(db, version, datos.vigente_desde, dia)
    db.commit()
    return horario_out(obtener_horario(db, horario.id), dia)
```

- [ ] **Paso 6: correr y verificar que pasan**

Run: `.venv/bin/pytest tests/test_api_horarios_alta.py -q && .venv/bin/pytest -q`
Expected: PASS y toda la suite verde.

- [ ] **Paso 7: commit**

```bash
git add backend/app/servicios/__init__.py backend/app/servicios/plantilla.py backend/app/repos/usuarios.py backend/app/api/horarios.py backend/tests/test_api_horarios_alta.py
git commit -m "$(cat <<'EOF'
POST /api/horarios: alta de un horario pactado con titular médico activo (D10, D23)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarea 5: POST /api/horarios/{id}/versiones (modificar y designar titular)

**Archivos:**
- Modificar: `backend/app/repos/horarios.py`, `backend/app/servicios/plantilla.py`, `backend/app/api/horarios.py`
- Modificar: `backend/tests/fabricas.py`, `backend/tests/test_repo_horarios.py`
- Crear: `backend/tests/test_api_horarios_versiones.py`, `backend/tests/test_concurrencia_staff.py`

**Interfaces:**
- Consume: `version_que_cubre`, `validar_desde`, `validar_fecha_ancla` (T2); `validar_titular`, `bloquear_usuario` (T4); `obtener_horario`, `a_vigencia`, `persona_out`, `version_out` (T3); `formatear_id_turno`, `Titular` (F1); `Turno` (F2).
- Produce:
  - `app.repos.horarios.datos_de(version: VersionHorario) -> DatosVersion`
  - `app.repos.horarios.bloquear_horario(sesion, horario_id: int) -> list[VersionHorario] | None`: bloquea la fila de `horario_pactado` y devuelve sus versiones releídas, ordenadas por `vigente_desde`; `None` si no existe.
  - `app.repos.horarios.nueva_version(sesion, horario_id, datos, desde) -> VersionHorario`: misma firma que en F1, pero ahora parte la versión que rige en `desde` y la nueva hereda su `vigente_hasta`.
  - `app.repos.horarios.TurnoAfectado(id: str, horario_id: int, fecha: date, inicio: datetime, fin: datetime, titular: Titular | None, asignado: Titular | None)`
  - `app.repos.horarios.turnos_afectados(sesion, horario_ids: Collection[int], desde: date) -> list[TurnoAfectado]`
  - `app.servicios.plantilla.ResultadoVersion(version: VersionHorario, turnos_afectados: list[TurnoAfectado])`
  - `app.servicios.plantilla.abrir_version(sesion, horario_id: int, cambios: Mapping[str, Any], desde: date, hoy: date) -> ResultadoVersion`. Las claves de `cambios` son campos de `DatosVersion`.
  - `app.servicios.plantilla._partir(sesion, horario_id: int, versiones: list[VersionHorario], cambios: Mapping[str, Any], desde: date) -> VersionHorario`, que la tarea 8 reutiliza.
  - `app.api.horarios`: `TurnoAfectadoOut`, `turno_afectado_out(t: TurnoAfectado) -> TurnoAfectadoOut`.
  - Fábricas: `guardar_turno(sesion, horario_id, fecha, asignado_id=None, consolidado_en=None) -> Turno` y `bloqueado_hasta_commit(primera: Session, accion: Callable[[], Any]) -> dict`.

- [ ] **Paso 1: fábricas de turno guardado y de concurrencia**

En `backend/tests/fabricas.py`, sumar a los imports `import threading`, `from collections.abc import Callable`, `from datetime import datetime`, `from typing import Any`, `from sqlalchemy import or_, select` y `Turno, VersionHorario` al import de `app.modelos`, y agregar:

```python
def guardar_turno(
    sesion: Session,
    horario_id: int,
    fecha: date,
    asignado_id: int | None = None,
    consolidado_en: datetime | None = None,
) -> Turno:
    """Turno materializado con la foto de la versión que rige `fecha` (D11), como lo guardaría F2b."""
    version = sesion.scalars(
        select(VersionHorario).where(
            VersionHorario.horario_id == horario_id,
            VersionHorario.vigente_desde <= fecha,
            or_(VersionHorario.vigente_hasta.is_(None), VersionHorario.vigente_hasta > fecha),
        )
    ).one()
    inicio = datetime.combine(fecha, version.hora_inicio, tzinfo=ZONA)
    turno = Turno(
        horario_id=horario_id,
        fecha=fecha,
        version_id=version.id,
        inicio=inicio,
        fin=inicio + timedelta(hours=version.duracion_horas),
        titular_id=version.medico_id,
        asignado_id=asignado_id,
        consolidado_en=consolidado_en,
    )
    guardar(sesion, turno)
    return turno


def bloqueado_hasta_commit(primera: Session, accion: Callable[[], Any]) -> dict:
    """Corre `accion` en otro hilo, verifica que espera los bloqueos de `primera`, confirma `primera`
    y devuelve lo que pasó en el hilo: {"valor": ...} o {"error": excepción}."""
    resultado: dict = {}

    def correr() -> None:
        try:
            resultado["valor"] = accion()
        except Exception as exc:  # noqa: BLE001 - la prueba inspecciona la excepción
            resultado["error"] = exc

    hilo = threading.Thread(target=correr)
    hilo.start()
    hilo.join(timeout=0.5)
    assert hilo.is_alive(), "la segunda transacción no esperó el bloqueo de la primera"
    primera.commit()
    hilo.join(timeout=10)
    assert not hilo.is_alive(), "la segunda transacción no terminó"
    return resultado
```

- [ ] **Paso 2: escribir las pruebas que fallan**

Al final de `backend/tests/test_repo_horarios.py`:

```python
def test_nueva_version_en_medio_hereda_el_fin_de_la_que_parte(sesion):
    horario = crear_horario(sesion, datos(), date(2026, 9, 7))
    nueva_version(sesion, horario.id, datos(hora=time(9)), date(2026, 11, 2))
    nueva_version(sesion, horario.id, datos(hora=time(8)), date(2026, 10, 19))
    versiones = sesion.scalars(
        select(VersionHorario).where(VersionHorario.horario_id == horario.id).order_by(VersionHorario.vigente_desde)
    ).all()
    assert [(v.vigente_desde, v.vigente_hasta, v.hora_inicio) for v in versiones] == [
        (date(2026, 9, 7), date(2026, 10, 19), time(7)),
        (date(2026, 10, 19), date(2026, 11, 2), time(8)),
        (date(2026, 11, 2), None, time(9)),
    ]
```

Crear `backend/tests/test_api_horarios_versiones.py`:

```python
from datetime import date, datetime, time

from app.repos.horarios import DatosVersion, nueva_version
from fabricas import ZONA, crear_horario_de_prueba, crear_usuario, encabezados, guardar_turno


def versiones(cliente, horario_id) -> list[dict]:
    [horario] = [h for h in cliente.get("/api/horarios").json() if h["id"] == horario_id]
    return horario["versiones"]


def test_cambio_de_hora_parte_la_version_y_el_calendario_lo_refleja(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id)  # martes 08:00, 12 h

    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "horaInicio": "09:00"})

    assert r.status_code == 201
    version = r.json()["version"]
    assert version["horaInicio"] == "09:00:00"
    assert version["medico"] == {"id": carlos.id, "nombre": "Carlos Lugones"}  # lo omitido se copia
    assert (version["vigenteDesde"], version["vigenteHasta"]) == ("2026-10-20", None)
    assert r.json()["turnosAfectados"] == []
    assert [(v["vigenteDesde"], v["vigenteHasta"]) for v in versiones(cliente, h.id)] == [
        ("2026-09-07", "2026-10-20"),
        ("2026-10-20", None),
    ]
    turnos = cliente.get("/api/turnos", params={"desde": "2026-10-13", "hasta": "2026-10-20"}).json()
    assert [t["inicio"] for t in turnos] == ["2026-10-13T08:00:00-03:00", "2026-10-20T09:00:00-03:00"]


def test_turnos_ya_guardados_conservan_su_foto_y_se_informan(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    paula = crear_usuario(sesion, "Paula Méndez")
    h = crear_horario_de_prueba(sesion, carlos.id)
    guardar_turno(sesion, h.id, date(2026, 10, 13))  # anterior al cambio: no es afectado
    guardar_turno(sesion, h.id, date(2026, 10, 20), asignado_id=paula.id)

    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "horaInicio": "09:00"})

    assert r.json()["turnosAfectados"] == [
        {
            "id": f"{h.id}:2026-10-20",
            "horarioId": h.id,
            "fecha": "2026-10-20",
            "inicio": "2026-10-20T08:00:00-03:00",  # la foto no se recalcula (D11, D12)
            "fin": "2026-10-20T20:00:00-03:00",
            "titular": {"id": carlos.id, "nombre": "Carlos Lugones"},
            "asignado": {"id": paula.id, "nombre": "Paula Méndez"},
        }
    ]


def test_turno_consolidado_hoy_no_es_afectado(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id, dia=1, hora=time(0), dur=6)  # lunes 00:00 a 06:00
    guardar_turno(sesion, h.id, date(2026, 10, 12), consolidado_en=datetime(2026, 10, 12, 7, tzinfo=ZONA))

    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-12", "horaInicio": "01:00"})

    assert r.status_code == 201
    assert r.json()["turnosAfectados"] == []


def test_designar_titular_en_un_horario_sin_titular(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, None)
    diego = crear_usuario(sesion, "Diego Sosa")

    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-12", "medicoId": diego.id})

    assert r.status_code == 201
    assert r.json()["version"]["medico"] == {"id": diego.id, "nombre": "Diego Sosa"}
    [horario] = [x for x in cliente.get("/api/horarios").json() if x["id"] == h.id]
    assert horario["estado"] == "CON_TITULAR"
    [turno] = cliente.get("/api/turnos", params={"desde": "2026-10-13", "hasta": "2026-10-13"}).json()
    assert turno["titular"] == {"id": diego.id, "nombre": "Diego Sosa"}


def test_medico_id_null_deja_el_horario_sin_titular(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id)

    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "medicoId": None})

    assert r.status_code == 201
    assert r.json()["version"]["medico"] is None
    [turno] = cliente.get("/api/turnos", params={"desde": "2026-10-20", "hasta": "2026-10-20"}).json()
    assert turno["titular"] is None


def test_cambio_antes_de_una_renegociacion_programada_rige_solo_hasta_ella(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id)
    programada = DatosVersion(
        medico_id=carlos.id, dia_semana=2, hora_inicio=time(10), duracion_horas=12,
        frecuencia_semanas=1, fecha_ancla=date(2026, 9, 7),
    )
    nueva_version(sesion, h.id, programada, date(2026, 11, 3))

    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "horaInicio": "09:00"})

    assert r.json()["version"]["vigenteHasta"] == "2026-11-03"
    assert [v["horaInicio"] for v in versiones(cliente, h.id)] == ["08:00:00", "09:00:00", "10:00:00"]


def test_cambio_en_el_pasado(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos Lugones").id)
    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-11", "horaInicio": "09:00"})
    assert (r.status_code, r.json()["codigo"]) == (422, "FECHA_PASADA")


def test_ya_hay_una_version_que_empieza_ese_dia(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos Lugones").id, desde=date(2026, 10, 20))
    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "horaInicio": "09:00"})
    assert (r.status_code, r.json()["codigo"]) == (409, "VERSION_EN_ESA_FECHA")


def test_horario_cerrado_no_admite_versiones(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos Lugones").id, hasta=date(2026, 10, 1))
    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "horaInicio": "09:00"})
    assert (r.status_code, r.json()["codigo"]) == (409, "HORARIO_SIN_VIGENCIA")


def test_version_igual_a_la_vigente(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos Lugones").id)
    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "horaInicio": "08:00"})
    assert (r.status_code, r.json()["codigo"]) == (422, "SIN_CAMBIOS")


def test_null_en_un_campo_que_no_es_el_medico(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos Lugones").id)
    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "diaSemana": None})
    assert (r.status_code, r.json()["codigo"]) == (422, "VALIDACION")


def test_fecha_ancla_nueva_que_no_es_lunes(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos Lugones").id)
    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "fechaAncla": "2026-10-13"})
    assert (r.status_code, r.json()["codigo"]) == (422, "FECHA_ANCLA_NO_LUNES")


def test_horario_inexistente(cliente, como_coordinador):
    r = cliente.post("/api/horarios/999999/versiones", json={"desde": "2026-10-20", "horaInicio": "09:00"})
    assert (r.status_code, r.json()["codigo"]) == (404, "HORARIO_NO_ENCONTRADO")


def test_designar_a_un_coordinador(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, None)
    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "medicoId": como_coordinador.id})
    assert (r.status_code, r.json()["codigo"]) == (422, "TITULAR_INVALIDO")


def test_un_medico_no_modifica_horarios(cliente, sesion, reloj):
    medico = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, medico.id)
    r = cliente.post(
        f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "horaInicio": "09:00"}, headers=encabezados(medico)
    )
    assert (r.status_code, r.json()["codigo"]) == (403, "SIN_PERMISO")
```

Crear `backend/tests/test_concurrencia_staff.py`:

```python
from datetime import date, time

import pytest

from app.errores import ErrorDominio
from app.servicios.plantilla import abrir_version
from fabricas import HOY, bloqueado_hasta_commit, crear_horario_de_prueba


@pytest.mark.commit_real
def test_dos_cambios_simultaneos_desde_la_misma_fecha(fabrica_sesiones):
    with fabrica_sesiones() as s:
        horario_id = crear_horario_de_prueba(s, None).id
        s.commit()

    with fabrica_sesiones() as s1, fabrica_sesiones() as s2:
        abrir_version(s1, horario_id, {"hora_inicio": time(9)}, date(2026, 10, 20), HOY)
        resultado = bloqueado_hasta_commit(
            s1, lambda: abrir_version(s2, horario_id, {"hora_inicio": time(10)}, date(2026, 10, 20), HOY)
        )

    assert isinstance(resultado.get("error"), ErrorDominio)
    assert resultado["error"].codigo == "VERSION_EN_ESA_FECHA"
```

- [ ] **Paso 3: correr y verificar que fallan**

Run: `.venv/bin/pytest tests/test_repo_horarios.py tests/test_api_horarios_versiones.py tests/test_concurrencia_staff.py -q`
Expected: FAIL. La del repo choca con `ex_version_horario_vigencia` (hoy se cierra la versión abierta, no la que rige ese día), la ruta no existe y `abrir_version` no se puede importar.

- [ ] **Paso 4: repos**

En `backend/app/repos/horarios.py`, sumar a los imports `from collections.abc import Collection`, `from datetime import date, datetime, time, timedelta`, `from sqlalchemy.orm import Session, aliased, selectinload`, `from app.dominio.calendario import Titular, VersionPlantilla, formatear_id_turno` y `Turno` al import de `app.modelos`. Reemplazar `nueva_version` y agregar las funciones nuevas:

```python
def datos_de(version: VersionHorario) -> DatosVersion:
    return DatosVersion(
        medico_id=version.medico_id,
        dia_semana=version.dia_semana,
        hora_inicio=version.hora_inicio,
        duracion_horas=version.duracion_horas,
        frecuencia_semanas=version.frecuencia_semanas,
        fecha_ancla=version.fecha_ancla,
    )


def bloquear_horario(sesion: Session, horario_id: int) -> list[VersionHorario] | None:
    """Bloquea el horario hasta el fin de la transacción y devuelve sus versiones releídas (regla 8).

    Bloquear la fila de horario_pactado, y no las versiones, serializa también a quien va a insertar
    una versión nueva: al despertar, el SELECT de versiones ya ve lo que confirmó el otro.
    """
    existe = sesion.scalar(select(HorarioPactado.id).where(HorarioPactado.id == horario_id).with_for_update())
    if existe is None:
        return None
    return list(
        sesion.scalars(
            select(VersionHorario)
            .where(VersionHorario.horario_id == horario_id)
            .order_by(VersionHorario.vigente_desde)
            .execution_options(populate_existing=True)
        )
    )


def nueva_version(sesion: Session, horario_id: int, datos: DatosVersion, desde: date) -> VersionHorario:
    """Parte en `desde` la versión que rige ese día y abre otra que hereda su fin de vigencia (D10).

    Si ninguna rige ese día, abre una sin fin. Las reglas están en app/dominio/plantilla.py; si igual
    choca, la rechazan las restricciones de la base.
    """
    cubre = sesion.scalars(
        select(VersionHorario)
        .where(
            VersionHorario.horario_id == horario_id,
            VersionHorario.vigente_desde <= desde,
            or_(VersionHorario.vigente_hasta.is_(None), VersionHorario.vigente_hasta > desde),
        )
        .with_for_update()
    ).one_or_none()
    hasta = None
    if cubre is not None:
        hasta = cubre.vigente_hasta
        cubre.vigente_hasta = desde
        sesion.flush()
    nueva = VersionHorario(horario_id=horario_id, vigente_desde=desde, vigente_hasta=hasta, **asdict(datos))
    sesion.add(nueva)
    sesion.flush()
    return nueva


@dataclass(frozen=True)
class TurnoAfectado:
    id: str
    horario_id: int
    fecha: date
    inicio: datetime
    fin: datetime
    titular: Titular | None
    asignado: Titular | None


def _titular(usuario: Usuario | None) -> Titular | None:
    return Titular(usuario.id, usuario.nombre) if usuario is not None else None


def turnos_afectados(sesion: Session, horario_ids: Collection[int], desde: date) -> list[TurnoAfectado]:
    """Turnos ya guardados desde `desde` y sin consolidar: conservan su foto aunque cambie la plantilla (D11, D12)."""
    if not horario_ids:
        return []
    titular = aliased(Usuario)
    asignado = aliased(Usuario)
    consulta = (
        select(Turno, titular, asignado)
        .outerjoin(titular, Turno.titular_id == titular.id)
        .outerjoin(asignado, Turno.asignado_id == asignado.id)
        .where(Turno.horario_id.in_(horario_ids), Turno.fecha >= desde, Turno.consolidado_en.is_(None))
        .order_by(Turno.inicio, Turno.horario_id)
    )
    return [
        TurnoAfectado(
            id=formatear_id_turno(turno.horario_id, turno.fecha),
            horario_id=turno.horario_id,
            fecha=turno.fecha,
            inicio=turno.inicio,
            fin=turno.fin,
            titular=_titular(t),
            asignado=_titular(a),
        )
        for turno, t, a in sesion.execute(consulta).all()
    ]
```

- [ ] **Paso 5: servicio**

En `backend/app/servicios/plantilla.py`, sumar a los imports `from collections.abc import Mapping`, `from dataclasses import dataclass, replace`, `from typing import Any`, `from app.dominio.plantilla import validar_desde, validar_fecha_ancla, version_que_cubre`, `VersionHorario` al import de `app.modelos` y `from app.repos.horarios import DatosVersion, TurnoAfectado, a_vigencia, bloquear_horario, crear_horario, datos_de, nueva_version, turnos_afectados`, y agregar:

```python
@dataclass(frozen=True)
class ResultadoVersion:
    version: VersionHorario
    turnos_afectados: list[TurnoAfectado]


def _partir(
    sesion: Session, horario_id: int, versiones: list[VersionHorario], cambios: Mapping[str, Any], desde: date
) -> VersionHorario:
    """Abre en `desde` una versión con `cambios`; lo demás se copia de la versión que rige ese día."""
    cubre_id = version_que_cubre([a_vigencia(v) for v in versiones], desde, horario_id).version_id
    actuales = datos_de(next(v for v in versiones if v.id == cubre_id))
    nuevos = replace(actuales, **cambios)
    if nuevos == actuales:
        raise ErrorDominio("SIN_CAMBIOS", "La versión nueva es igual a la que rige ese día.")
    validar_fecha_ancla(nuevos.fecha_ancla)
    return nueva_version(sesion, horario_id, nuevos, desde)


def abrir_version(
    sesion: Session, horario_id: int, cambios: Mapping[str, Any], desde: date, hoy: date
) -> ResultadoVersion:
    """Renegociación, designación de titular o horario sin titular, desde `desde` (D10, D12, D24).

    `cambios` usa los nombres de DatosVersion; medico_id None deja el horario sin titular.
    """
    validar_desde(desde, hoy)
    if cambios.get("medico_id") is not None:
        validar_titular(sesion, cambios["medico_id"])  # primero el usuario, después el horario
    versiones = bloquear_horario(sesion, horario_id)
    if versiones is None:
        raise ErrorDominio("HORARIO_NO_ENCONTRADO", "No existe ese horario.", 404)
    version = _partir(sesion, horario_id, versiones, cambios, desde)
    return ResultadoVersion(version, turnos_afectados(sesion, [horario_id], desde))
```

- [ ] **Paso 6: endpoint**

En `backend/app/api/horarios.py`, sumar a los imports `from typing import Any`, `from pydantic import Field, model_validator`, `from app.config import get_settings`, `from app.errores import ErrorDominio`, `TurnoAfectado` al import de `app.repos.horarios` y `abrir_version` al import de `app.servicios.plantilla`, y agregar:

```python
class TurnoAfectadoOut(Esquema):
    id: str
    horario_id: int
    fecha: date
    inicio: datetime
    fin: datetime
    titular: PersonaOut | None
    asignado: PersonaOut | None


def turno_afectado_out(turno: TurnoAfectado) -> TurnoAfectadoOut:
    zona = get_settings().zona
    return TurnoAfectadoOut(
        id=turno.id,
        horario_id=turno.horario_id,
        fecha=turno.fecha,
        inicio=turno.inicio.astimezone(zona),
        fin=turno.fin.astimezone(zona),
        titular=persona_out(turno.titular),
        asignado=persona_out(turno.asignado),
    )


class VersionIn(Esquema):
    """Solo lo que cambia; lo omitido se copia de la versión que rige en `desde`. medicoId null = sin titular."""

    desde: date
    medico_id: int | None = None
    dia_semana: int | None = Field(default=None, ge=1, le=7)
    hora_inicio: time | None = None
    duracion_horas: int | None = Field(default=None, ge=1, le=24)
    frecuencia_semanas: int | None = Field(default=None, ge=1, le=52)
    fecha_ancla: date | None = None

    @model_validator(mode="after")
    def _solo_el_medico_admite_null(self) -> "VersionIn":
        nulos = sorted(c for c in self.model_fields_set if c != "medico_id" and getattr(self, c) is None)
        if nulos:
            raise ValueError(f"Solo medicoId admite null; vinieron en null: {', '.join(nulos)}")
        return self

    def cambios(self) -> dict[str, Any]:
        return {campo: getattr(self, campo) for campo in self.model_fields_set if campo != "desde"}


class VersionNuevaOut(Esquema):
    version: VersionOut
    turnos_afectados: list[TurnoAfectadoOut]


@router.post("/horarios/{horario_id}/versiones", response_model=VersionNuevaOut, status_code=201)
def nueva(
    horario_id: int,
    datos: VersionIn,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> VersionNuevaOut:
    """Modifica un horario o designa su titular con una versión nueva (D10, D24) y lista los turnos afectados (D12)."""
    resultado = abrir_version(db, horario_id, datos.cambios(), datos.desde, hoy(reloj))
    db.commit()
    return VersionNuevaOut(
        version=version_out(resultado.version),
        turnos_afectados=[turno_afectado_out(t) for t in resultado.turnos_afectados],
    )
```

- [ ] **Paso 7: correr y verificar que pasan**

Run: `.venv/bin/pytest tests/test_repo_horarios.py tests/test_api_horarios_versiones.py tests/test_concurrencia_staff.py -q && .venv/bin/pytest -q`
Expected: PASS y toda la suite verde. Las pruebas de F1 de `nueva_version` (incluida la de la misma fecha, que sigue rechazando la base) y `test_seed` pasan sin cambios.

- [ ] **Paso 8: commit**

```bash
git add backend/app/repos/horarios.py backend/app/servicios/plantilla.py backend/app/api/horarios.py backend/tests/fabricas.py backend/tests/test_repo_horarios.py backend/tests/test_api_horarios_versiones.py backend/tests/test_concurrencia_staff.py
git commit -m "$(cat <<'EOF'
POST /api/horarios/{id}/versiones: modificar o designar titular con turnos afectados (D10, D12, D24)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarea 6: POST /api/horarios/{id}/cierre

**Archivos:**
- Modificar: `backend/app/servicios/plantilla.py`, `backend/app/api/horarios.py`
- Crear: `backend/tests/test_api_horarios_cierre.py`

**Interfaces:**
- Consume: `version_que_cubre`, `hay_version_posterior`, `validar_desde` (T2); `bloquear_horario`, `turnos_afectados`, `a_vigencia` (T5); `horario_out`, `obtener_horario`, `turno_afectado_out` (T3, T5).
- Produce: `app.servicios.plantilla.cerrar_horario(sesion, horario_id: int, desde: date, hoy: date) -> list[TurnoAfectado]`. `desde` es el primer día en que el horario ya no rige.

- [ ] **Paso 1: escribir las pruebas que fallan**

Crear `backend/tests/test_api_horarios_cierre.py`:

```python
from datetime import date, time

from app.repos.horarios import DatosVersion, nueva_version
from fabricas import crear_horario_de_prueba, crear_usuario, encabezados, guardar_turno


def test_cierre_corta_la_vigencia_y_el_calendario(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id)

    r = cliente.post(f"/api/horarios/{h.id}/cierre", json={"desde": "2026-10-20"})

    assert r.status_code == 200
    assert r.json()["horario"]["estado"] == "CON_TITULAR"  # hoy todavía rige
    assert r.json()["horario"]["versiones"][-1]["vigenteHasta"] == "2026-10-20"
    assert r.json()["turnosAfectados"] == []
    turnos = cliente.get("/api/turnos", params={"desde": "2026-10-13", "hasta": "2026-10-27"}).json()
    assert [t["fecha"] for t in turnos] == ["2026-10-13"]


def test_cierre_desde_hoy_deja_el_horario_cerrado(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos Lugones").id)
    r = cliente.post(f"/api/horarios/{h.id}/cierre", json={"desde": "2026-10-12"})
    assert r.json()["horario"]["estado"] == "CERRADO"


def test_cierre_informa_los_turnos_guardados(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id)
    guardar_turno(sesion, h.id, date(2026, 10, 27))
    r = cliente.post(f"/api/horarios/{h.id}/cierre", json={"desde": "2026-10-20"})
    assert [t["id"] for t in r.json()["turnosAfectados"]] == [f"{h.id}:2026-10-27"]


def test_horario_ya_cerrado(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos Lugones").id)
    cliente.post(f"/api/horarios/{h.id}/cierre", json={"desde": "2026-10-20"})
    r = cliente.post(f"/api/horarios/{h.id}/cierre", json={"desde": "2026-10-20"})
    assert (r.status_code, r.json()["codigo"]) == (409, "HORARIO_SIN_VIGENCIA")


def test_cierre_con_una_version_posterior(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id)
    programada = DatosVersion(
        medico_id=carlos.id, dia_semana=2, hora_inicio=time(10), duracion_horas=12,
        frecuencia_semanas=1, fecha_ancla=date(2026, 9, 7),
    )
    nueva_version(sesion, h.id, programada, date(2026, 11, 3))
    r = cliente.post(f"/api/horarios/{h.id}/cierre", json={"desde": "2026-10-20"})
    assert (r.status_code, r.json()["codigo"]) == (409, "VERSION_POSTERIOR_EXISTENTE")


def test_cierre_en_el_pasado(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos Lugones").id)
    r = cliente.post(f"/api/horarios/{h.id}/cierre", json={"desde": "2026-10-11"})
    assert (r.status_code, r.json()["codigo"]) == (422, "FECHA_PASADA")


def test_cierre_de_horario_inexistente(cliente, como_coordinador):
    r = cliente.post("/api/horarios/999999/cierre", json={"desde": "2026-10-20"})
    assert (r.status_code, r.json()["codigo"]) == (404, "HORARIO_NO_ENCONTRADO")


def test_un_medico_no_cierra_horarios(cliente, sesion, reloj):
    medico = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, medico.id)
    r = cliente.post(f"/api/horarios/{h.id}/cierre", json={"desde": "2026-10-20"}, headers=encabezados(medico))
    assert (r.status_code, r.json()["codigo"]) == (403, "SIN_PERMISO")
```

- [ ] **Paso 2: correr y verificar que fallan**

Run: `.venv/bin/pytest tests/test_api_horarios_cierre.py -q`
Expected: FAIL con 404 (la ruta no existe).

- [ ] **Paso 3: servicio**

En `backend/app/servicios/plantilla.py`, sumar `hay_version_posterior` al import de `app.dominio.plantilla` y agregar:

```python
def cerrar_horario(sesion: Session, horario_id: int, desde: date, hoy: date) -> list[TurnoAfectado]:
    """El horario deja de regir en `desde` (D24). No borra versiones: corta la vigencia de la que rige ese día."""
    validar_desde(desde, hoy)
    versiones = bloquear_horario(sesion, horario_id)
    if versiones is None:
        raise ErrorDominio("HORARIO_NO_ENCONTRADO", "No existe ese horario.", 404)
    vigencias = [a_vigencia(v) for v in versiones]
    cubre_id = version_que_cubre(vigencias, desde, horario_id).version_id
    if hay_version_posterior(vigencias, desde):
        raise ErrorDominio(
            "VERSION_POSTERIOR_EXISTENTE",
            f"El horario {horario_id} tiene una versión que empieza después del {desde:%d/%m/%Y}: cerrarlo la dejaría suelta.",
            409,
        )
    next(v for v in versiones if v.id == cubre_id).vigente_hasta = desde
    sesion.flush()
    return turnos_afectados(sesion, [horario_id], desde)
```

- [ ] **Paso 4: endpoint**

En `backend/app/api/horarios.py`, sumar `cerrar_horario` al import de `app.servicios.plantilla` y agregar:

```python
class CierreIn(Esquema):
    desde: date  # primer día en que el horario ya no rige


class CierreOut(Esquema):
    horario: HorarioOut
    turnos_afectados: list[TurnoAfectadoOut]


@router.post("/horarios/{horario_id}/cierre", response_model=CierreOut)
def cerrar(
    horario_id: int,
    datos: CierreIn,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> CierreOut:
    """Cierra un horario pactado (D24) y lista los turnos ya guardados que quedan afuera (D12)."""
    dia = hoy(reloj)
    afectados = cerrar_horario(db, horario_id, datos.desde, dia)
    db.commit()
    return CierreOut(
        horario=horario_out(obtener_horario(db, horario_id), dia),
        turnos_afectados=[turno_afectado_out(t) for t in afectados],
    )
```

- [ ] **Paso 5: correr y verificar que pasan**

Run: `.venv/bin/pytest tests/test_api_horarios_cierre.py -q && .venv/bin/pytest -q`
Expected: PASS y toda la suite verde.

- [ ] **Paso 6: commit**

```bash
git add backend/app/servicios/plantilla.py backend/app/api/horarios.py backend/tests/test_api_horarios_cierre.py
git commit -m "$(cat <<'EOF'
POST /api/horarios/{id}/cierre: cerrar un horario pactado con turnos afectados (D12, D24)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarea 7: PATCH /api/usuarios/{id} (activar un médico pendiente)

**Archivos:**
- Crear: `backend/app/servicios/usuarios.py`
- Modificar: `backend/app/api/usuarios.py`
- Crear: `backend/tests/test_api_usuarios_activacion.py`

**Interfaces:**
- Consume: `bloquear_usuario` (T4); `TurnoAfectado` (T5); `TurnoAfectadoOut`, `turno_afectado_out` (T5); `usuario_out`, `versiones_no_terminadas_por_medico` (T3).
- Produce:
  - `app.servicios.usuarios.ResultadoCambio(usuario: Usuario, horarios_sin_titular: list[int] = [], turnos_afectados: list[TurnoAfectado] = [])`
  - `app.servicios.usuarios._bloquear(sesion, usuario_id: int) -> Usuario`: 404 `USUARIO_NO_ENCONTRADO`; 409 `USUARIO_DADO_DE_BAJA`.
  - `app.servicios.usuarios.activar(sesion, usuario_id: int) -> ResultadoCambio`
  - `app.api.usuarios`: `CambioUsuarioIn`, `CambioUsuarioOut`, `cambio_out(db, resultado, dia) -> CambioUsuarioOut`.

- [ ] **Paso 1: escribir las pruebas que fallan**

Crear `backend/tests/test_api_usuarios_activacion.py`:

```python
import pytest

from app.modelos import EstadoUsuario
from fabricas import crear_usuario, encabezados


def test_activar_un_medico_pendiente(cliente, sesion, como_coordinador):
    nuevo = crear_usuario(sesion, "Médico nuevo", estado=EstadoUsuario.PENDIENTE)

    r = cliente.patch(f"/api/usuarios/{nuevo.id}", json={"estado": "ACTIVO"})

    assert r.status_code == 200
    assert r.json()["usuario"]["estado"] == "ACTIVO"
    assert r.json()["horariosSinTitular"] == []
    assert r.json()["turnosAfectados"] == []
    entra = cliente.get("/api/turnos", params={"desde": "2026-10-12", "hasta": "2026-10-12"}, headers=encabezados(nuevo))
    assert entra.status_code == 200


def test_activar_a_alguien_ya_activo(cliente, sesion, como_coordinador):
    activo = crear_usuario(sesion, "Carlos Lugones")
    r = cliente.patch(f"/api/usuarios/{activo.id}", json={"estado": "ACTIVO"})
    assert (r.status_code, r.json()["codigo"]) == (409, "YA_ACTIVO")


def test_activar_una_baja(cliente, sesion, como_coordinador):
    baja = crear_usuario(sesion, "Se fue", estado=EstadoUsuario.BAJA)
    r = cliente.patch(f"/api/usuarios/{baja.id}", json={"estado": "ACTIVO"})
    assert (r.status_code, r.json()["codigo"]) == (409, "USUARIO_DADO_DE_BAJA")


def test_activar_un_usuario_inexistente(cliente, como_coordinador):
    r = cliente.patch("/api/usuarios/999999", json={"estado": "ACTIVO"})
    assert (r.status_code, r.json()["codigo"]) == (404, "USUARIO_NO_ENCONTRADO")


@pytest.mark.parametrize("estado", ["BAJA", "PENDIENTE"])
def test_patch_solo_pasa_a_activo(cliente, sesion, como_coordinador, estado):
    activo = crear_usuario(sesion, "Carlos Lugones")
    r = cliente.patch(f"/api/usuarios/{activo.id}", json={"estado": estado})
    assert (r.status_code, r.json()["codigo"]) == (422, "VALIDACION")


def test_patch_sin_cambios(cliente, sesion, como_coordinador):
    activo = crear_usuario(sesion, "Carlos Lugones")
    r = cliente.patch(f"/api/usuarios/{activo.id}", json={})
    assert (r.status_code, r.json()["codigo"]) == (422, "SIN_CAMBIOS")


def test_un_medico_no_activa_cuentas(cliente, sesion, reloj):
    medico = crear_usuario(sesion, "Carlos Lugones")
    nuevo = crear_usuario(sesion, "Médico nuevo", estado=EstadoUsuario.PENDIENTE)
    r = cliente.patch(f"/api/usuarios/{nuevo.id}", json={"estado": "ACTIVO"}, headers=encabezados(medico))
    assert (r.status_code, r.json()["codigo"]) == (403, "SIN_PERMISO")
```

- [ ] **Paso 2: correr y verificar que fallan**

Run: `.venv/bin/pytest tests/test_api_usuarios_activacion.py -q`
Expected: FAIL con 405 (la ruta PATCH no existe).

- [ ] **Paso 3: servicio**

Crear `backend/app/servicios/usuarios.py`:

```python
"""Operaciones de staff sobre usuarios (D23, D24, D26, D30). No hacen commit; nunca borran un usuario."""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.errores import ErrorDominio
from app.modelos import EstadoUsuario, Usuario
from app.repos.horarios import TurnoAfectado
from app.repos.usuarios import bloquear_usuario


@dataclass(frozen=True)
class ResultadoCambio:
    usuario: Usuario
    horarios_sin_titular: list[int] = field(default_factory=list)
    turnos_afectados: list[TurnoAfectado] = field(default_factory=list)


def _bloquear(sesion: Session, usuario_id: int) -> Usuario:
    usuario = bloquear_usuario(sesion, usuario_id)
    if usuario is None:
        raise ErrorDominio("USUARIO_NO_ENCONTRADO", "No existe ese usuario.", 404)
    if usuario.estado == EstadoUsuario.BAJA:
        raise ErrorDominio("USUARIO_DADO_DE_BAJA", "El usuario está dado de baja.", 409)
    return usuario


def activar(sesion: Session, usuario_id: int) -> ResultadoCambio:
    """Un médico que se registró sin código queda PENDIENTE hasta que un coordinador lo activa (D30)."""
    usuario = _bloquear(sesion, usuario_id)
    if usuario.estado != EstadoUsuario.PENDIENTE:
        raise ErrorDominio("YA_ACTIVO", "El usuario ya está activo.", 409)
    usuario.estado = EstadoUsuario.ACTIVO
    sesion.flush()
    return ResultadoCambio(usuario)
```

- [ ] **Paso 4: endpoint**

En `backend/app/api/usuarios.py`, sumar a los imports `from typing import Literal`, `from app.api.horarios import TurnoAfectadoOut, turno_afectado_out`, `from app.errores import ErrorDominio` y `from app.servicios.usuarios import ResultadoCambio, activar`, y agregar:

```python
class CambioUsuarioIn(Esquema):
    estado: Literal["ACTIVO"] | None = None  # la baja tiene su propia ruta


class CambioUsuarioOut(Esquema):
    usuario: UsuarioStaffOut
    horarios_sin_titular: list[int]
    turnos_afectados: list[TurnoAfectadoOut]


def cambio_out(db: Session, resultado: ResultadoCambio, dia: date) -> CambioUsuarioOut:
    usuario = resultado.usuario
    versiones = versiones_no_terminadas_por_medico(db, dia, usuario.id).get(usuario.id, [])
    return CambioUsuarioOut(
        usuario=usuario_out(usuario, versiones),
        horarios_sin_titular=resultado.horarios_sin_titular,
        turnos_afectados=[turno_afectado_out(t) for t in resultado.turnos_afectados],
    )


@router.patch("/usuarios/{usuario_id}", response_model=CambioUsuarioOut)
def modificar(
    usuario_id: int,
    datos: CambioUsuarioIn,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> CambioUsuarioOut:
    """Activa a un médico pendiente (D26, D30)."""
    if datos.estado is None:
        raise ErrorDominio("SIN_CAMBIOS", "No se pidió ningún cambio.")
    resultado = activar(db, usuario_id)
    db.commit()
    return cambio_out(db, resultado, hoy(reloj))
```

- [ ] **Paso 5: correr y verificar que pasan**

Run: `.venv/bin/pytest tests/test_api_usuarios_activacion.py -q && .venv/bin/pytest -q`
Expected: PASS y toda la suite verde.

- [ ] **Paso 6: commit**

```bash
git add backend/app/servicios/usuarios.py backend/app/api/usuarios.py backend/tests/test_api_usuarios_activacion.py
git commit -m "$(cat <<'EOF'
PATCH /api/usuarios/{id}: activar un médico pendiente (D26, D30)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarea 8: POST /api/usuarios/{id}/baja

**Archivos:**
- Modificar: `backend/app/repos/horarios.py`, `backend/app/servicios/plantilla.py`, `backend/app/servicios/usuarios.py`, `backend/app/api/usuarios.py`
- Crear: `backend/tests/test_api_usuarios_baja.py`

**Interfaces:**
- Consume: `_partir`, `bloquear_horario`, `turnos_afectados` (T5); `validar_desde` (T2); `_bloquear`, `ResultadoCambio`, `cambio_out` (T7).
- Produce:
  - `app.repos.horarios.versiones_del_medico_desde(sesion, medico_id: int, desde: date) -> list[VersionHorario]`: versiones del médico que rigen en `desde` o después.
  - `app.servicios.plantilla.dejar_sin_titular(sesion, medico_id: int, desde: date, hoy: date) -> tuple[list[int], list[TurnoAfectado]]`. Precondición: el médico ya está bloqueado por quien llama.
  - `app.servicios.usuarios.dar_de_baja(sesion, usuario_id: int, fecha_baja: date, hoy: date) -> ResultadoCambio`.

- [ ] **Paso 1: escribir las pruebas que fallan**

Crear `backend/tests/test_api_usuarios_baja.py`:

```python
from datetime import date, time

from app.modelos import EstadoUsuario, RolUsuario
from app.repos.horarios import DatosVersion, nueva_version
from fabricas import crear_horario_de_prueba, crear_usuario, encabezados, guardar_turno


def titulares(cliente, desde, hasta) -> list[tuple[str, str | None]]:
    turnos = cliente.get("/api/turnos", params={"desde": desde, "hasta": hasta}).json()
    return [(t["fecha"], t["titular"]["nombre"] if t["titular"] else None) for t in turnos]


def test_baja_hoy_deja_sus_horarios_sin_titular_desde_mañana(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    martes = crear_horario_de_prueba(sesion, carlos.id, dia=2)
    lunes = crear_horario_de_prueba(sesion, carlos.id, dia=1, hora=time(20))

    r = cliente.post(f"/api/usuarios/{carlos.id}/baja", json={"fechaBaja": "2026-10-12"})

    assert r.status_code == 200
    assert r.json()["usuario"]["estado"] == "BAJA"
    assert r.json()["usuario"]["fechaBaja"] == "2026-10-12"
    assert r.json()["horariosSinTitular"] == sorted([martes.id, lunes.id])
    # D24: activo hasta la fecha de baja inclusive; la guardia del lunes 12 sigue siendo suya.
    assert titulares(cliente, "2026-10-12", "2026-10-13") == [
        ("2026-10-12", "Carlos Lugones"),
        ("2026-10-13", None),
    ]
    [h] = [x for x in cliente.get("/api/horarios").json() if x["id"] == martes.id]
    assert [(v["medico"] and v["medico"]["id"], v["vigenteDesde"], v["vigenteHasta"]) for v in h["versiones"]] == [
        (carlos.id, "2026-09-07", "2026-10-13"),
        (None, "2026-10-13", None),
    ]


def test_baja_futura_conserva_las_guardias_hasta_esa_fecha(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    crear_horario_de_prueba(sesion, carlos.id)  # martes

    r = cliente.post(f"/api/usuarios/{carlos.id}/baja", json={"fechaBaja": "2026-10-20"})

    assert r.status_code == 200
    assert titulares(cliente, "2026-10-13", "2026-10-27") == [
        ("2026-10-13", "Carlos Lugones"),
        ("2026-10-20", "Carlos Lugones"),
        ("2026-10-27", None),
    ]
    entra = cliente.get("/api/turnos", params={"desde": "2026-10-12", "hasta": "2026-10-12"}, headers=encabezados(carlos))
    assert entra.status_code == 200  # sigue entrando hasta el 20/10 inclusive (decisión 2)
    assert [x["vigenteHasta"] for x in r.json()["usuario"]["horarios"]] == ["2026-10-21"]


def test_baja_informa_los_turnos_guardados_de_sus_horarios(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id)
    guardar_turno(sesion, h.id, date(2026, 10, 20))

    r = cliente.post(f"/api/usuarios/{carlos.id}/baja", json={"fechaBaja": "2026-10-12"})

    [afectado] = r.json()["turnosAfectados"]
    assert afectado["id"] == f"{h.id}:2026-10-20"
    assert afectado["titular"] == {"id": carlos.id, "nombre": "Carlos Lugones"}  # la foto no cambia (D12)


def test_baja_respeta_una_version_futura_de_otro_medico(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    paula = crear_usuario(sesion, "Paula Méndez")
    h = crear_horario_de_prueba(sesion, carlos.id)
    de_paula = DatosVersion(
        medico_id=paula.id, dia_semana=2, hora_inicio=time(8), duracion_horas=12,
        frecuencia_semanas=1, fecha_ancla=date(2026, 9, 7),
    )
    nueva_version(sesion, h.id, de_paula, date(2026, 11, 3))

    cliente.post(f"/api/usuarios/{carlos.id}/baja", json={"fechaBaja": "2026-10-12"})

    [x] = [x for x in cliente.get("/api/horarios").json() if x["id"] == h.id]
    assert [(v["medico"] and v["medico"]["id"], v["vigenteDesde"], v["vigenteHasta"]) for v in x["versiones"]] == [
        (carlos.id, "2026-09-07", "2026-10-13"),
        (None, "2026-10-13", "2026-11-03"),
        (paula.id, "2026-11-03", None),
    ]


def test_baja_con_una_version_futura_propia(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id)
    nueva_version(
        sesion, h.id,
        DatosVersion(medico_id=carlos.id, dia_semana=2, hora_inicio=time(9), duracion_horas=12,
                     frecuencia_semanas=1, fecha_ancla=date(2026, 9, 7)),
        date(2026, 11, 3),
    )
    r = cliente.post(f"/api/usuarios/{carlos.id}/baja", json={"fechaBaja": "2026-10-12"})
    assert (r.status_code, r.json()["codigo"]) == (409, "VERSION_FUTURA_DEL_MEDICO")
    assert cliente.get("/api/usuarios").json()[0]["estado"] == "ACTIVO"  # no quedó nada a medias


def test_baja_de_un_pendiente(cliente, sesion, como_coordinador):
    pendiente = crear_usuario(sesion, "Registro equivocado", estado=EstadoUsuario.PENDIENTE)
    r = cliente.post(f"/api/usuarios/{pendiente.id}/baja", json={"fechaBaja": "2026-10-12"})
    assert r.status_code == 200
    assert r.json()["usuario"]["estado"] == "BAJA"
    assert pendiente.id in [u["id"] for u in cliente.get("/api/usuarios").json()]  # nunca se borra (D24)


def test_baja_en_el_pasado(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    r = cliente.post(f"/api/usuarios/{carlos.id}/baja", json={"fechaBaja": "2026-10-11"})
    assert (r.status_code, r.json()["codigo"]) == (422, "FECHA_PASADA")


def test_baja_de_un_coordinador(cliente, sesion, como_coordinador):
    otro = crear_usuario(sesion, "Otro coordinador", rol=RolUsuario.COORDINADOR)
    r = cliente.post(f"/api/usuarios/{otro.id}/baja", json={"fechaBaja": "2026-10-12"})
    assert (r.status_code, r.json()["codigo"]) == (422, "BAJA_SOLO_MEDICOS")


def test_baja_repetida(cliente, sesion, como_coordinador):
    baja = crear_usuario(sesion, "Se fue", estado=EstadoUsuario.BAJA)
    r = cliente.post(f"/api/usuarios/{baja.id}/baja", json={"fechaBaja": "2026-10-12"})
    assert (r.status_code, r.json()["codigo"]) == (409, "USUARIO_DADO_DE_BAJA")


def test_baja_de_usuario_inexistente(cliente, como_coordinador):
    r = cliente.post("/api/usuarios/999999/baja", json={"fechaBaja": "2026-10-12"})
    assert (r.status_code, r.json()["codigo"]) == (404, "USUARIO_NO_ENCONTRADO")


def test_un_medico_no_da_de_baja(cliente, sesion, reloj):
    medico = crear_usuario(sesion, "Carlos Lugones")
    otro = crear_usuario(sesion, "Paula Méndez")
    r = cliente.post(f"/api/usuarios/{otro.id}/baja", json={"fechaBaja": "2026-10-12"}, headers=encabezados(medico))
    assert (r.status_code, r.json()["codigo"]) == (403, "SIN_PERMISO")
```

Nota sobre `test_baja_con_una_version_futura_propia`: el endpoint no confirma si hay error. La sesión de prueba es compartida, así que la última aserción verifica el estado dentro de la misma transacción: el error se lanza antes de cambiar el estado. El orden de `listar_usuarios` (Carlos antes que Enzo) hace que `[0]` sea Carlos.

- [ ] **Paso 2: correr y verificar que fallan**

Run: `.venv/bin/pytest tests/test_api_usuarios_baja.py -q`
Expected: FAIL con 404 (la ruta no existe).

- [ ] **Paso 3: repo**

En `backend/app/repos/horarios.py`, agregar:

```python
def versiones_del_medico_desde(sesion: Session, medico_id: int, desde: date) -> list[VersionHorario]:
    """Versiones del médico que rigen en `desde` o después."""
    return list(
        sesion.scalars(
            select(VersionHorario)
            .where(
                VersionHorario.medico_id == medico_id,
                or_(VersionHorario.vigente_hasta.is_(None), VersionHorario.vigente_hasta > desde),
            )
            .order_by(VersionHorario.horario_id, VersionHorario.vigente_desde)
        )
    )
```

- [ ] **Paso 4: `dejar_sin_titular`**

En `backend/app/servicios/plantilla.py`, sumar `versiones_del_medico_desde` al import de `app.repos.horarios` y agregar:

```python
def dejar_sin_titular(
    sesion: Session, medico_id: int, desde: date, hoy: date
) -> tuple[list[int], list[TurnoAfectado]]:
    """Abre en `desde` una versión sin titular en cada horario del médico (D23, D24).

    Quien llama ya bloqueó al médico: nadie puede designarlo titular mientras tanto. Cada horario se bloquea
    antes de mirar sus versiones, así un cambio simultáneo de otro coordinador no se pierde.
    """
    validar_desde(desde, hoy)
    horario_ids = sorted({v.horario_id for v in versiones_del_medico_desde(sesion, medico_id, desde)})
    for horario_id in horario_ids:
        versiones = bloquear_horario(sesion, horario_id)
        futura = next((v for v in versiones if v.medico_id == medico_id and v.vigente_desde >= desde), None)
        if futura is not None:
            raise ErrorDominio(
                "VERSION_FUTURA_DEL_MEDICO",
                f"El médico es titular de una versión del horario {horario_id} que empieza el "
                f"{futura.vigente_desde:%d/%m/%Y}: cambiala antes de continuar.",
                409,
            )
        _partir(sesion, horario_id, versiones, {"medico_id": None}, desde)
    return horario_ids, turnos_afectados(sesion, horario_ids, desde)
```

- [ ] **Paso 5: `dar_de_baja`**

En `backend/app/servicios/usuarios.py`, sumar `from datetime import date, timedelta`, `RolUsuario` al import de `app.modelos` y `from app.servicios.plantilla import dejar_sin_titular`, y agregar:

```python
def dar_de_baja(sesion: Session, usuario_id: int, fecha_baja: date, hoy: date) -> ResultadoCambio:
    """Baja definitiva de un médico (D24). `fecha_baja` es su último día activo (decisión 1 del plan de F5).

    Sus horarios quedan sin titular desde el día siguiente. El estado pasa a BAJA ya, pero la cuenta
    entra hasta `fecha_baja` inclusive (app/auth.py). Nunca se borra el usuario.
    """
    usuario = _bloquear(sesion, usuario_id)
    if usuario.rol != RolUsuario.MEDICO:
        raise ErrorDominio("BAJA_SOLO_MEDICOS", "Solo se da de baja a un médico; un coordinador pasa antes a médico.")
    if fecha_baja < hoy:
        raise ErrorDominio("FECHA_PASADA", f"La fecha de baja no puede ser anterior a hoy ({hoy:%d/%m/%Y}).")
    horarios, afectados = dejar_sin_titular(sesion, usuario.id, fecha_baja + timedelta(days=1), hoy)
    usuario.estado = EstadoUsuario.BAJA
    usuario.fecha_baja = fecha_baja
    sesion.flush()
    return ResultadoCambio(usuario, horarios, afectados)
```

- [ ] **Paso 6: endpoint**

En `backend/app/api/usuarios.py`, sumar `dar_de_baja` al import de `app.servicios.usuarios` y agregar:

```python
class BajaIn(Esquema):
    fecha_baja: date  # último día activo (D24)


@router.post("/usuarios/{usuario_id}/baja", response_model=CambioUsuarioOut)
def baja(
    usuario_id: int,
    datos: BajaIn,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> CambioUsuarioOut:
    """Da de baja a un médico: sus horarios quedan sin titular desde el día siguiente (D24)."""
    dia = hoy(reloj)
    resultado = dar_de_baja(db, usuario_id, datos.fecha_baja, dia)
    db.commit()
    return cambio_out(db, resultado, dia)
```

- [ ] **Paso 7: correr y verificar que pasan**

Run: `.venv/bin/pytest tests/test_api_usuarios_baja.py -q && .venv/bin/pytest -q`
Expected: PASS y toda la suite verde.

- [ ] **Paso 8: commit**

```bash
git add backend/app/repos/horarios.py backend/app/servicios/plantilla.py backend/app/servicios/usuarios.py backend/app/api/usuarios.py backend/tests/test_api_usuarios_baja.py
git commit -m "$(cat <<'EOF'
POST /api/usuarios/{id}/baja: baja de un médico con horarios sin titular desde el día siguiente (D24)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarea 9: cambio de rol con al menos un coordinador activo

**Archivos:**
- Modificar: `backend/app/repos/usuarios.py`, `backend/app/servicios/usuarios.py`, `backend/app/api/usuarios.py`
- Crear: `backend/tests/test_api_usuarios_rol.py`
- Modificar: `backend/tests/test_concurrencia_staff.py`

**Interfaces:**
- Consume: `dejar_sin_titular` (T8); `activar`, `ResultadoCambio`, `cambio_out`, `CambioUsuarioIn` (T7); `bloqueado_hasta_commit`, `HOY` (T5, T3).
- Produce:
  - `app.repos.usuarios.bloquear_con_coordinadores(sesion, usuario_id: int) -> tuple[Usuario | None, list[Usuario]]`
  - `app.servicios.usuarios.cambiar_rol(sesion, usuario_id: int, rol: RolUsuario, hoy: date) -> ResultadoCambio`
  - `CambioUsuarioIn` suma `rol: RolUsuario | None = None`.

- [ ] **Paso 1: escribir las pruebas que fallan**

Crear `backend/tests/test_api_usuarios_rol.py`:

```python
from datetime import date

from app.modelos import EstadoUsuario, RolUsuario
from fabricas import crear_horario_de_prueba, crear_usuario, encabezados, guardar_turno


def test_coordinador_pasa_a_medico_si_queda_otro(cliente, sesion, como_coordinador):
    otro = crear_usuario(sesion, "Otro coordinador", rol=RolUsuario.COORDINADOR)

    r = cliente.patch(f"/api/usuarios/{otro.id}", json={"rol": "MEDICO"})

    assert r.status_code == 200
    assert r.json()["usuario"]["rol"] == "MEDICO"
    sin_permiso = cliente.get("/api/usuarios", headers=encabezados(otro))
    assert sin_permiso.json()["codigo"] == "SIN_PERMISO"


def test_el_ultimo_coordinador_no_deja_de_serlo(cliente, como_coordinador):
    r = cliente.patch(f"/api/usuarios/{como_coordinador.id}", json={"rol": "MEDICO"})
    assert (r.status_code, r.json()["codigo"]) == (422, "ULTIMO_COORDINADOR")


def test_un_coordinador_pendiente_no_cuenta_como_activo(cliente, sesion, como_coordinador):
    crear_usuario(sesion, "Coordinador sin activar", rol=RolUsuario.COORDINADOR, estado=EstadoUsuario.PENDIENTE)
    r = cliente.patch(f"/api/usuarios/{como_coordinador.id}", json={"rol": "MEDICO"})
    assert (r.status_code, r.json()["codigo"]) == (422, "ULTIMO_COORDINADOR")


def test_medico_que_pasa_a_coordinador_deja_sus_horarios_sin_titular_desde_mañana(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id)  # martes
    guardar_turno(sesion, h.id, date(2026, 10, 20))

    r = cliente.patch(f"/api/usuarios/{carlos.id}", json={"rol": "COORDINADOR"})

    assert r.status_code == 200
    assert r.json()["usuario"]["rol"] == "COORDINADOR"
    assert r.json()["horariosSinTitular"] == [h.id]
    assert [t["id"] for t in r.json()["turnosAfectados"]] == [f"{h.id}:2026-10-20"]
    [turno] = cliente.get("/api/turnos", params={"desde": "2026-10-13", "hasta": "2026-10-13"}).json()
    assert turno["titular"] is None


def test_activar_y_promover_en_un_solo_pedido(cliente, sesion, como_coordinador):
    nuevo = crear_usuario(sesion, "Nueva coordinadora", estado=EstadoUsuario.PENDIENTE)
    r = cliente.patch(f"/api/usuarios/{nuevo.id}", json={"estado": "ACTIVO", "rol": "COORDINADOR"})
    assert r.status_code == 200
    assert (r.json()["usuario"]["estado"], r.json()["usuario"]["rol"]) == ("ACTIVO", "COORDINADOR")


def test_mismo_rol(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    r = cliente.patch(f"/api/usuarios/{carlos.id}", json={"rol": "MEDICO"})
    assert (r.status_code, r.json()["codigo"]) == (422, "SIN_CAMBIOS")


def test_cambio_de_rol_de_una_baja(cliente, sesion, como_coordinador):
    baja = crear_usuario(sesion, "Se fue", estado=EstadoUsuario.BAJA)
    r = cliente.patch(f"/api/usuarios/{baja.id}", json={"rol": "COORDINADOR"})
    assert (r.status_code, r.json()["codigo"]) == (409, "USUARIO_DADO_DE_BAJA")


def test_rol_desconocido(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    r = cliente.patch(f"/api/usuarios/{carlos.id}", json={"rol": "ADMIN"})
    assert (r.status_code, r.json()["codigo"]) == (422, "VALIDACION")


def test_un_medico_no_cambia_roles(cliente, sesion, reloj):
    medico = crear_usuario(sesion, "Carlos Lugones")
    r = cliente.patch(f"/api/usuarios/{medico.id}", json={"rol": "COORDINADOR"}, headers=encabezados(medico))
    assert (r.status_code, r.json()["codigo"]) == (403, "SIN_PERMISO")
```

Al final de `backend/tests/test_concurrencia_staff.py` (sumar `from app.modelos import RolUsuario`, `from app.servicios.usuarios import cambiar_rol` y `crear_usuario` al import de fabricas):

```python
@pytest.mark.commit_real
def test_dos_coordinadores_no_pueden_quitarse_el_rol_a_la_vez(fabrica_sesiones):
    with fabrica_sesiones() as s:
        ana = crear_usuario(s, "Ana", rol=RolUsuario.COORDINADOR)
        beto = crear_usuario(s, "Beto", rol=RolUsuario.COORDINADOR)
        s.commit()
        ana_id, beto_id = ana.id, beto.id

    with fabrica_sesiones() as s1, fabrica_sesiones() as s2:
        cambiar_rol(s1, beto_id, RolUsuario.MEDICO, HOY)  # Ana le quita el rol a Beto
        resultado = bloqueado_hasta_commit(s1, lambda: cambiar_rol(s2, ana_id, RolUsuario.MEDICO, HOY))

    assert isinstance(resultado.get("error"), ErrorDominio)
    assert resultado["error"].codigo == "ULTIMO_COORDINADOR"
```

- [ ] **Paso 2: correr y verificar que fallan**

Run: `.venv/bin/pytest tests/test_api_usuarios_rol.py tests/test_concurrencia_staff.py -q`
Expected: FAIL. `rol` no se acepta (422 `SIN_CAMBIOS` o `VALIDACION`) y `cambiar_rol` no se puede importar.

- [ ] **Paso 3: bloqueo de coordinadores**

En `backend/app/repos/usuarios.py`, cambiar el import a `from sqlalchemy import and_, func, or_, select` y `from app.modelos import EstadoUsuario, RolUsuario, Usuario`, y agregar:

```python
def bloquear_con_coordinadores(sesion: Session, usuario_id: int) -> tuple[Usuario | None, list[Usuario]]:
    """Bloquea, en orden de id, al usuario y a los coordinadores activos (D23, regla 8).

    Un solo SELECT ... ORDER BY id FOR UPDATE: dos cambios de rol simultáneos toman los bloqueos en el
    mismo orden (sin deadlock) y el segundo, al despertar, vuelve a evaluar el WHERE y ya no cuenta a quien
    dejó de ser coordinador.
    """
    filas = sesion.scalars(
        select(Usuario)
        .where(
            or_(
                Usuario.id == usuario_id,
                and_(Usuario.rol == RolUsuario.COORDINADOR, Usuario.estado == EstadoUsuario.ACTIVO),
            )
        )
        .order_by(Usuario.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    usuario = next((u for u in filas if u.id == usuario_id), None)
    coordinadores = [u for u in filas if u.rol == RolUsuario.COORDINADOR and u.estado == EstadoUsuario.ACTIVO]
    return usuario, coordinadores
```

- [ ] **Paso 4: `cambiar_rol`**

En `backend/app/servicios/usuarios.py`, sumar `bloquear_con_coordinadores` al import de `app.repos.usuarios` y agregar:

```python
def cambiar_rol(sesion: Session, usuario_id: int, rol: RolUsuario, hoy: date) -> ResultadoCambio:
    """Roles excluyentes (D23). Siempre queda al menos un coordinador activo.

    Un médico que pasa a coordinador deja sus horarios sin titular desde mañana, en la misma transacción:
    hoy todavía hace su guardia (decisión 4 del plan de F5).
    """
    usuario, coordinadores = bloquear_con_coordinadores(sesion, usuario_id)
    if usuario is None:
        raise ErrorDominio("USUARIO_NO_ENCONTRADO", "No existe ese usuario.", 404)
    if usuario.estado == EstadoUsuario.BAJA:
        raise ErrorDominio("USUARIO_DADO_DE_BAJA", "El usuario está dado de baja.", 409)
    if usuario.rol == rol:
        raise ErrorDominio("SIN_CAMBIOS", "El usuario ya tiene ese rol.")
    if rol == RolUsuario.MEDICO:
        if not any(c.id != usuario.id for c in coordinadores):
            raise ErrorDominio("ULTIMO_COORDINADOR", "Tiene que quedar al menos un coordinador activo (D23).")
        usuario.rol = RolUsuario.MEDICO
        sesion.flush()
        return ResultadoCambio(usuario)
    horarios, afectados = dejar_sin_titular(sesion, usuario.id, hoy + timedelta(days=1), hoy)
    usuario.rol = RolUsuario.COORDINADOR
    sesion.flush()
    return ResultadoCambio(usuario, horarios, afectados)
```

- [ ] **Paso 5: endpoint**

En `backend/app/api/usuarios.py`, sumar `cambiar_rol` al import de `app.servicios.usuarios`. En `CambioUsuarioIn`, agregar el campo:

```python
    rol: RolUsuario | None = None
```

y reemplazar el cuerpo de `modificar`:

```python
    """Activa a un médico pendiente (D26, D30) y/o cambia el rol (D23), en ese orden."""
    if datos.estado is None and datos.rol is None:
        raise ErrorDominio("SIN_CAMBIOS", "No se pidió ningún cambio.")
    dia = hoy(reloj)
    resultado = activar(db, usuario_id) if datos.estado is not None else None
    if datos.rol is not None:
        resultado = cambiar_rol(db, usuario_id, datos.rol, dia)
    db.commit()
    return cambio_out(db, resultado, dia)
```

- [ ] **Paso 6: correr y verificar que pasan**

Run: `.venv/bin/pytest tests/test_api_usuarios_rol.py tests/test_concurrencia_staff.py -q && .venv/bin/pytest -q`
Expected: PASS y toda la suite verde.

- [ ] **Paso 7: commit**

```bash
git add backend/app/repos/usuarios.py backend/app/servicios/usuarios.py backend/app/api/usuarios.py backend/tests/test_api_usuarios_rol.py backend/tests/test_concurrencia_staff.py
git commit -m "$(cat <<'EOF'
Cambio de rol con al menos un coordinador activo y horarios sin titular al pasar a coordinador (D23)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarea 10: documentación

**Archivos:**
- Modificar: `CLAUDE.md`, `backend/CLAUDE.md`, `docs/decisiones-arquitectura.md`, `docs/prompts-principales.md`

- [ ] **Paso 1: `CLAUDE.md` de la raíz**

En "Endpoints principales", reemplazar el punto 5 por:

```markdown
5. Staff y plantilla (solo coordinadores): GET /usuarios, PATCH /usuarios/{id} (activar, cambiar rol), POST /usuarios/{id}/baja, GET /horarios, POST /horarios, POST /horarios/{id}/versiones (modificar o designar titular; devuelve los turnos afectados), POST /horarios/{id}/cierre. Las altas de usuarios son por registro (D30).
```

- [ ] **Paso 2: `backend/CLAUDE.md`**

En "Estructura", después del punto 3 (`app/repos/`), insertar y renumerar:

```markdown
4. `app/servicios/`: operaciones que combinan reglas de `app/dominio/` y consultas de `app/repos/` (staff y plantilla). No hacen commit; lo hace el router.
```

En "Convenciones", agregar:

```markdown
11. Orden de bloqueos (regla 8): primero filas de `usuario`, después filas de `horario_pactado`. Varios usuarios se bloquean en un solo SELECT ordenado por id (`bloquear_con_coordinadores`). Un horario se bloquea con `bloquear_horario`, que relee sus versiones.
12. "Hoy" es `hoy(reloj)` de `app/reloj.py`, en la zona del servicio. Ningún cambio de plantilla empieza antes de hoy.
13. Fábricas de F5: `crear_horario_de_prueba`, `guardar_turno` (turno materializado con la foto de su versión), `bloqueado_hasta_commit` (pruebas `commit_real` de bloqueos), `HOY` y la fixture `como_coordinador`.
14. Una cuenta BAJA entra hasta su `fecha_baja` inclusive (D24); `ck_usuario_fecha_baja` obliga a que estado BAJA y fecha vayan juntos.
```

- [ ] **Paso 3: `docs/decisiones-arquitectura.md`**

Al final de D23, agregar:

```markdown
Ajuste del 7/10/2026 (plan de F5): el cambio de médico a coordinador deja sus horarios sin titular desde el día siguiente en la misma acción. "Al menos un coordinador activo" se garantiza bloqueando en la base las filas de los coordinadores activos.
```

Al final de D24, agregar:

```markdown
Ajuste del 7/10/2026 (plan de F5): la fecha de baja es el último día activo; los horarios quedan sin titular desde el día siguiente. El estado pasa a BAJA al registrarla y la cuenta entra hasta esa fecha inclusive. No se registran bajas con fecha pasada. Solo se da de baja a médicos; un coordinador pasa antes a médico. El coordinador también puede cerrar un horario (POST /horarios/{id}/cierre).
```

- [ ] **Paso 4: `docs/prompts-principales.md`**

Antes de "## Próximas entradas", agregar:

```markdown
## 5. F5: staff, backend

Fecha: 7/10/2026.
Herramienta: Claude Code con Superpowers (writing-plans; sin brainstorming ni spec propio: el plan se apoya en las decisiones de arquitectura).
Prompt:

> Partí de la branch feature/f2-cimientos (todavía no está mergeada en main) y creá a partir de ella la branch feature/f5-staff-backend. Leé backend/CLAUDE.md y el documento de decisiones de arquitectura en docs, especialmente D10, D12, D23, D24 y D26. Vamos a hacer la fase F5 "staff, backend": endpoints solo para coordinadores para listar usuarios con rol, estado y horarios vigentes; activar un médico pendiente; cargar un horario pactado; modificarlo creando una nueva versión y devolviendo la lista de turnos afectados (D12); cerrar un horario; cambiar el rol respetando D23 (siempre al menos un coordinador activo, y un médico que pasa a coordinador deja antes sus horarios sin titular); dar de baja a un médico (D24: fecha de baja, sus horarios quedan sin titular con una versión nueva) y designar nuevo titular en un horario sin titular. Restricciones: no toques nada de vacantes, postulaciones ni consolidación, que son de Mariano. La parte de D24 que reabre como vacantes las coberturas aceptadas por el médico dado de baja tiene que usar la función de generar vacante de Mariano, que todavía no existe: dejala como última tarea del plan, marcada como dependiente. Si necesitás una migración, numerala a continuación de la de F2. Usá Superpowers: escribí el plan en docs/superpowers/plans y un commit por tarea. Solo escribí el plan, mostrámelo para aprobarlo y commitealo. No ejecutes nada hasta que te lo pida.

Resultado: plan en `docs/superpowers/plans/2026-10-07-f5-staff-backend.md`, con 11 tareas (la última, dependiente de F2b) y 16 decisiones, entre ellas una ambigüedad de D24 (fecha de baja como último día activo) para aprobar antes de ejecutar.
```

- [ ] **Paso 5: verificación final**

Run (desde la raíz): `docker compose up -d --wait`
Run (desde `backend/`): `.venv/bin/pytest -q`
Expected: toda la suite pasa. No se tocó el frontend: no hace falta Playwright.

Run: `grep -rn "datetime.now\|date.today\|time.time" backend/app`
Expected: solo aparece `app/reloj.py`.

Run: `git diff --stat main...HEAD -- backend/app/modelos/turno.py backend/app/modelos/evento.py`
Expected: sin cambios de F5 sobre vacantes, postulaciones ni bitácora.

- [ ] **Paso 6: commit**

```bash
git add CLAUDE.md backend/CLAUDE.md docs/decisiones-arquitectura.md docs/prompts-principales.md
git commit -m "$(cat <<'EOF'
Documentación de F5: endpoints de staff, capa de servicios, orden de bloqueos y ajustes de D23 y D24

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarea 11 (DEPENDIENTE de F2b): la baja y el cambio de rol reabren como vacantes las coberturas aceptadas

> **No ejecutar hasta que exista la función de generar vacante de Mariano (F2b) en la branch base.** Esta tarea no implementa vacantes: llama a esa función. Si su firma o su comportamiento no coinciden con lo que se supone abajo, frenar y preguntar al equipo antes de adaptar.

D24: "Las coberturas que el médico había aceptado para turnos posteriores se reabren como vacantes comunes". Lo mismo vale para un médico que pasa a coordinador (D23: el coordinador no cubre vacantes).

**Supuestos sobre la función de Mariano, a confirmar en el paso 1:**
- Nombre y lugar: algo como `app/servicios/vacantes.py::generar_vacante`.
- Recibe la sesión, el turno (o su id "horarioId:fecha"), el actor, el motivo y el reloj; no hace commit.
- Un coordinador puede generarla sobre un turno ajeno (D15).
- Sobre un turno con asignado, deja la vacante ABIERTA y el turno sin asignado, y escribe `VACANTE_GENERADA` y sus notificaciones en la misma transacción (D16, D22).

**Archivos:**
- Modificar: `backend/app/repos/horarios.py` (o `app/repos/turnos.py` si F2b lo creó), `backend/app/servicios/usuarios.py`, `backend/app/api/usuarios.py`
- Crear: `backend/tests/test_baja_reabre_coberturas.py`

**Interfaces:**
- Consume: la función de generar vacante de F2b; `dar_de_baja`, `cambiar_rol`, `ResultadoCambio` (T8, T9).
- Produce:
  - `coberturas_desde(sesion, medico_id: int, desde: date) -> list[Turno]`: turnos con `asignado_id = medico_id`, fecha desde `desde` y sin consolidar.
  - `ResultadoCambio` suma `coberturas_reabiertas: list[TurnoAfectado]`. `dar_de_baja(sesion, usuario_id, fecha_baja, actor: Usuario, reloj: Reloj)` y `cambiar_rol(sesion, usuario_id, rol, actor: Usuario, reloj: Reloj)` reciben el actor y el reloj en lugar de `hoy`.
  - `CambioUsuarioOut` suma `coberturasReabiertas: list[TurnoAfectadoOut]`.

- [ ] **Paso 1: confirmar la función de Mariano**

Run: `grep -rn "def generar_vacante" backend/app`
Expected: aparece la función. Leer su firma, su docstring y sus pruebas, y verificar los cuatro supuestos de arriba. Si alguno no se cumple, frenar y preguntar. Anotar la firma real en esta tarea antes de seguir.

Firma real (8/10/2026): `generar_vacante(sesion, turno_id: str, actor: Usuario, motivo: str | None, reloj: Reloj, zona: ZoneInfo) -> ResultadoVacante`, en `app/servicios/vacantes.py`. Recibe el id "horarioId:fecha" (no el turno) y suma la zona (`get_settings().zona`). Los cuatro supuestos se cumplen: no hace commit; `puede_generar` admite al coordinador sobre un turno ajeno; borra el asignado y escribe `VACANTE_GENERADA` con `asignado_anterior_id` en la misma transacción; solo notifica si la vacante es urgente (D05). Ajuste al paso 5: se reabre después de `dejar_sin_titular` y del cambio de estado o rol, no antes, porque la convención 19 de `backend/CLAUDE.md` bloquea los turnos después de los horarios; `generar_vacante` no mira el estado del médico, así que ese orden no la rechaza.

- [ ] **Paso 2: escribir las pruebas que fallan**

Crear `backend/tests/test_baja_reabre_coberturas.py`:

```python
from datetime import date, datetime, time

from sqlalchemy import select

from app.modelos import EstadoVacante, Turno, Vacante
from fabricas import ZONA, crear_horario_de_prueba, crear_usuario, guardar_turno


def vacante_abierta(sesion, turno_id) -> Vacante | None:
    return sesion.scalar(select(Vacante).where(Vacante.turno_id == turno_id, Vacante.estado == EstadoVacante.ABIERTA))


def test_baja_reabre_las_coberturas_posteriores(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    paula = crear_usuario(sesion, "Paula Méndez")
    de_paula = crear_horario_de_prueba(sesion, paula.id, dia=4)  # jueves
    cubre_el_15 = guardar_turno(sesion, de_paula.id, date(2026, 10, 15), asignado_id=carlos.id)

    r = cliente.post(f"/api/usuarios/{carlos.id}/baja", json={"fechaBaja": "2026-10-12"})

    assert r.status_code == 200
    assert [t["id"] for t in r.json()["coberturasReabiertas"]] == [f"{de_paula.id}:2026-10-15"]
    assert vacante_abierta(sesion, cubre_el_15.id) is not None
    assert sesion.get(Turno, cubre_el_15.id).asignado_id is None


def test_baja_futura_conserva_las_coberturas_hasta_su_fecha(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    paula = crear_usuario(sesion, "Paula Méndez")
    de_paula = crear_horario_de_prueba(sesion, paula.id, dia=4)
    antes = guardar_turno(sesion, de_paula.id, date(2026, 10, 15), asignado_id=carlos.id)
    despues = guardar_turno(sesion, de_paula.id, date(2026, 10, 22), asignado_id=carlos.id)

    cliente.post(f"/api/usuarios/{carlos.id}/baja", json={"fechaBaja": "2026-10-15"})

    assert vacante_abierta(sesion, antes.id) is None
    assert vacante_abierta(sesion, despues.id) is not None


def test_cobertura_consolidada_no_se_reabre(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    paula = crear_usuario(sesion, "Paula Méndez")
    de_paula = crear_horario_de_prueba(sesion, paula.id, dia=1, hora=time(0), dur=6)
    hecha = guardar_turno(
        sesion, de_paula.id, date(2026, 10, 12), asignado_id=carlos.id,
        consolidado_en=datetime(2026, 10, 12, 7, tzinfo=ZONA),
    )

    cliente.post(f"/api/usuarios/{carlos.id}/baja", json={"fechaBaja": "2026-10-12"})

    assert vacante_abierta(sesion, hecha.id) is None


def test_medico_que_pasa_a_coordinador_libera_sus_coberturas(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    paula = crear_usuario(sesion, "Paula Méndez")
    de_paula = crear_horario_de_prueba(sesion, paula.id, dia=4)
    cubre = guardar_turno(sesion, de_paula.id, date(2026, 10, 15), asignado_id=carlos.id)

    r = cliente.patch(f"/api/usuarios/{carlos.id}", json={"rol": "COORDINADOR"})

    assert [t["id"] for t in r.json()["coberturasReabiertas"]] == [f"{de_paula.id}:2026-10-15"]
    assert vacante_abierta(sesion, cubre.id) is not None
```

- [ ] **Paso 3: correr y verificar que fallan**

Run: `.venv/bin/pytest tests/test_baja_reabre_coberturas.py -q`
Expected: FAIL. La respuesta no tiene `coberturasReabiertas` y no se crea la vacante.

- [ ] **Paso 4: consulta de coberturas**

Agregar (en `app/repos/horarios.py`, o en `app/repos/turnos.py` si F2b lo creó):

```python
def coberturas_desde(sesion: Session, medico_id: int, desde: date) -> list[Turno]:
    """Turnos que el médico quedó cubriendo desde `desde` y que todavía no se consolidaron (D24)."""
    return list(
        sesion.scalars(
            select(Turno)
            .where(Turno.asignado_id == medico_id, Turno.fecha >= desde, Turno.consolidado_en.is_(None))
            .order_by(Turno.inicio, Turno.horario_id)
            .with_for_update()
        )
    )
```

- [ ] **Paso 5: reabrir en la baja y en el cambio de rol**

En `backend/app/servicios/usuarios.py`, agregar el campo `coberturas_reabiertas: list[TurnoAfectado] = field(default_factory=list)` a `ResultadoCambio` y una función privada. Ajustar la llamada a la firma real anotada en el paso 1:

```python
def _reabrir_coberturas(sesion: Session, medico: Usuario, desde: date, actor: Usuario, reloj: Reloj) -> list[TurnoAfectado]:
    """D24: las coberturas aceptadas desde `desde` se reabren como vacantes comunes, con la función de F2b."""
    reabiertas = []
    for turno in coberturas_desde(sesion, medico.id, desde):
        generar_vacante(sesion, turno, actor=actor, motivo=f"Baja de {medico.nombre}", reloj=reloj)
        reabiertas.append(turno_a_afectado(turno, medico))
    return reabiertas
```

`turno_a_afectado(turno, asignado_anterior)` arma un `TurnoAfectado` con el asignado que tenía el turno antes de reabrirlo. Va en el mismo módulo del repo que `turnos_afectados`, reutilizando `_titular` y `formatear_id_turno`, y carga el titular con `sesion.get(Usuario, turno.titular_id)`.

Cambiar las firmas de `dar_de_baja(sesion, usuario_id, fecha_baja, actor, reloj)` y `cambiar_rol(sesion, usuario_id, rol, actor, reloj)`: calculan `dia = hoy(reloj)` donde antes recibían `hoy`. Antes de cambiar estado o rol, llaman a `_reabrir_coberturas(sesion, usuario, desde, actor, reloj)` con el mismo `desde` que pasan a `dejar_sin_titular` (`fecha_baja + 1` en la baja, `dia + 1` en el cambio de rol) y suman el resultado a `ResultadoCambio`. Si `generar_vacante` rechaza la llamada por el estado del médico, reabrir antes de cambiarlo resuelve el orden.

En `backend/app/api/usuarios.py`: `baja` y `modificar` reciben `coordinador: Usuario = Depends(requiere_coordinador)` (sin guion bajo) y pasan `coordinador, reloj`. `CambioUsuarioOut` suma `coberturas_reabiertas: list[TurnoAfectadoOut]` y `cambio_out` lo completa. Actualizar `tests/test_concurrencia_staff.py` a la firma nueva de `cambiar_rol`, con el actor `ana` (o `beto`) y `RelojFijo(datetime(2026, 10, 12, 9, tzinfo=ZONA))`.

- [ ] **Paso 6: correr y verificar que pasan**

Run: `.venv/bin/pytest tests/test_baja_reabre_coberturas.py -q && .venv/bin/pytest -q`
Expected: PASS y toda la suite verde, incluidas las pruebas de vacantes de F2b.

- [ ] **Paso 7: commit**

```bash
git add backend/app/repos backend/app/servicios/usuarios.py backend/app/api/usuarios.py backend/tests/test_baja_reabre_coberturas.py backend/tests/test_concurrencia_staff.py
git commit -m "$(cat <<'EOF'
La baja y el cambio a coordinador reabren como vacantes las coberturas aceptadas (D23, D24)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Después de la tarea 10: revisión de toda la branch

Revisión de código de `feature/f5-staff-backend` contra `feature/f2-cimientos` (superpowers:requesting-code-review), con foco en las cinco líneas del "Foco de revisión" y en el orden de bloqueos. Los hallazgos que no bloquean el merge se anotan en `docs/bitacora-de-desvios.md`. Después, pull request contra main (una vez mergeado el #7), revisado por otro integrante en GitHub. La tarea 11 entra en un pull request aparte cuando exista F2b.
