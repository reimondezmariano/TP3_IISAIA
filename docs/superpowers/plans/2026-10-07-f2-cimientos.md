# F2: cimientos (autenticación, registro y modelo operativo). Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Objetivo:** dejar listos los cimientos sobre los que otro integrante implementa vacantes y postulaciones: sesión con Supabase Auth (D06, D07), `POST /api/registro` con código de coordinación (D30), `GET /api/me`, dependencias de permisos, y las tablas Turno, Vacante, Postulacion, EventoTurno y Notificacion (D08 a D25) en una única migración.

**Arquitectura:** el frontend inicia sesión contra Supabase Auth y manda el token de acceso en `Authorization: Bearer`. `app/auth.py` verifica el token (HS256 con el secreto del proyecto o ES256/RS256 con las claves públicas JWKS de Supabase, según el algoritmo del token) y expone tres dependencias encadenadas: `identidad_actual` (token válido), `usuario_registrado` (token vinculado a un Usuario) y `usuario_actual` (Usuario ACTIVO), más `requiere_coordinador`. El esquema nuevo es la migración `0002`, escrita a mano en SQL como la `0001`; las invariantes que no dependen de reglas de negocio (unicidad, vacante abierta única, bitácora solo de agregar, alerta única por umbral) quedan en la base. No se implementa ninguna regla de negocio de vacantes, postulaciones, asignación ni consolidación: eso lo hace otro integrante sobre estas tablas.

**Tecnologías:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, psycopg 3, PyJWT (con `cryptography`), pytest.

**Spec:** no hay spec propio de F2: el plan se apoya directamente en `docs/decisiones-arquitectura.md` (D06, D07, D08 a D25, D27, D28, D30) y en el `CLAUDE.md` de la raíz. Las elecciones que esas decisiones dejan abiertas están en la sección "Decisiones de este plan".

**Ejecución (definida por el equipo el 7/10/2026):** en la misma sesión, con superpowers:executing-plans, tarea por tarea y un commit por tarea. Al terminar las seis tareas, revisión de código de toda la branch (superpowers:requesting-code-review) antes de abrir el pull request.

## Restricciones globales

- Toda la API va bajo `/api`. Errores con formato `{"codigo": "...", "mensaje": "..."}`: 401 sin sesión, 403 sin permiso, 404 inexistente, 409 conflicto, 422 regla de negocio o validación (`VALIDACION`).
- JSON en camelCase mediante `app/api/esquemas.py::Esquema` (alias de Pydantic).
- Nunca se guardan contraseñas en tablas propias (D06). El backend solo verifica tokens.
- El código de coordinación vive solo en la variable de entorno `CODIGO_COORDINACION`; nunca en el repositorio ni en el frontend (D30).
- RLS activado sin políticas en cada tabla nueva (D07).
- Nada en `backend/app/` consulta la hora del sistema fuera de `app/reloj.py` (D27; lo verifica `tests/test_sin_hora_del_sistema.py`). Las columnas de instantes de dominio (`creada_en` de vacante, postulación y notificación, `ocurrido_en` del evento) no tienen valor por defecto en la base: las completa la aplicación con el reloj inyectable.
- La bitácora solo se agrega (regla 6 del CLAUDE.md): un trigger rechaza UPDATE y DELETE sobre `evento_turno`.
- Nunca se borra un usuario (D24): ninguna FK nueva usa `ON DELETE CASCADE`.
- Pruebas siempre contra el Postgres local de docker-compose (puerto 5433), nunca SQLite. Comandos del backend desde `backend/`.
- Un commit por tarea, en español, citando las decisiones. Cada commit termina con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Branch: `feature/f2-cimientos`.

## Decisiones de este plan

Elecciones que las decisiones de arquitectura dejan abiertas. El equipo aprobó el plan y estas decisiones el 7/10/2026. La decisión 1 se aparta a propósito de la regla 10 del CLAUDE.md, por el motivo que se explica ahí, y se aprobó de forma explícita.

1. **Vencimiento del token con la hora real.** PyJWT controla `exp` con la hora del sistema, no con el reloj inyectable. Es deliberado: Supabase emite el token en tiempo real, y si el vencimiento usara el reloj de demo (D27), adelantarlo dos días cerraría todas las sesiones en plena demo. No viola la prueba de D27 porque la consulta de la hora ocurre dentro de la biblioteca, no en `app/`.
2. **Algoritmo según el token.** Los proyectos nuevos de Supabase firman con claves asimétricas (ES256, JWKS público en `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`); los anteriores, con el secreto HS256. El verificador acepta los dos según la configuración disponible y rechaza cualquier otro algoritmo, incluido `none`.
3. **Registro después del alta en Supabase.** El frontend crea la cuenta en Supabase Auth (`signUp`), obtiene el token y llama a `POST /api/registro` con `{nombre, codigoCoordinacion?}`. El email sale del token, nunca del cuerpo.
4. **Vinculación por email (D28).** Si ya existe un Usuario con ese email y sin cuenta vinculada (los que carga el seed, como Enzo), el registro lo vincula y conserva su nombre, rol y estado; responde 200. El código se valida igual (uno incorrecto es 422), pero no cambia el rol de un usuario existente: pasar de médico a coordinador exige antes dejar sus horarios sin titular (D23), y eso es de la pantalla de staff. **Corregida tras la revisión de código:** vincular un Usuario cargado con rol COORDINADOR exige el código válido (422 `CODIGO_REQUERIDO` si falta), porque sin confirmación de email (D06) cualquiera podría crear la cuenta de Supabase con ese email.
5. **Código incorrecto es error, no médico pendiente.** Un código ingresado e incorrecto responde 422 `CODIGO_INVALIDO` en lugar de crear silenciosamente un médico pendiente. La comparación ignora mayúsculas y espacios en los extremos. Si `CODIGO_COORDINACION` está vacío, ningún código es válido.
6. **Cuentas sin acceso.** `GET /api/me` responde a cualquier usuario registrado (también PENDIENTE o BAJA), para que la interfaz muestre "esperando activación". El resto de los endpoints exige estado ACTIVO: PENDIENTE responde 403 `CUENTA_PENDIENTE` y BAJA 403 `CUENTA_DADA_DE_BAJA`. Una cuenta de Supabase sin Usuario responde 403 `USUARIO_NO_REGISTRADO`. Se usa el estado, no `fecha_baja`: pasar a BAJA es del flujo de baja (D24).
7. **`GET /api/turnos` pasa a exigir sesión.** Cumple el contrato ("token en todos los pedidos"). `GET /api/health` sigue público, así que la prueba e2e del frontend no cambia.
8. **Urgente se calcula.** La vacante no guarda `urgente`: se calcula como `turno.inicio - vacante.creada_en < 24 h` (D15). Ambos valores son fijos, así que el resultado no cambia con el tiempo.
9. **Estado de la vacante:** `ABIERTA`, `RETIRADA`, `CUBIERTA`, `SIN_COBERTURA`, con `cerrada_en` obligatorio en todo estado distinto de ABIERTA.
10. **Postulación única por (turno, médico)** incluso retirada: volver a postularse reactiva la misma fila (lo implementa quien haga postulaciones).
11. **Versión del turno coherente con su horario:** FK compuesta `(version_id, horario_id)` hacia `version_horario (id, horario_id)`, para que un turno no pueda apuntar a la versión de otro horario.
12. **Alertas escalonadas únicas por umbral (D19):** índice único parcial sobre `(turno_id, datos->>'umbral')` para los eventos `ALERTA_SIN_COBERTURA`, y un CHECK que obliga a informar el umbral (sin él, los NULL no chocan en el índice). Valores esperados del umbral: `"48H"`, `"24H"`, `"INICIO"`.
13. **Tipo de notificación como texto.** Las decisiones no fijan la lista de tipos; `notificacion.tipo` es texto en MAYÚSCULAS para que F4 los defina sin cambiar el esquema.
14. **El seed conserva los vínculos con Supabase Auth (tarea 6).** Al recargar, cada usuario de ejemplo recupera el `auth_id` que tenía el usuario con el mismo email (sin distinguir mayúsculas). Los usuarios que no son de ejemplo (por ejemplo, médicos que se registraron desde la app) se borran igual que hoy; si vuelven a entrar, `POST /api/registro` los da de alta de nuevo.

## Foco de revisión

Casos que las decisiones implican y que es más probable que fallen en uso real; cada uno tiene su prueba en la tarea indicada.

1. **Token sin firma (`alg: none`) o firmado con otra clave:** debe responder 401 `TOKEN_INVALIDO`, nunca aceptarse. Tarea 2, `test_tokens_invalidos`.
2. **Token vencido:** 401 `TOKEN_VENCIDO` (la interfaz renueva la sesión), no 500 ni `TOKEN_INVALIDO`. Tarea 2, `test_token_vencido` y `test_bearer_vencido_responde_token_vencido`.
3. **Enzo (cargado por el seed) se registra con su email:** se vincula al Usuario existente, conserva COORDINADOR y ACTIVO, y no choca con el índice único de email. Tarea 4, `test_email_cargado_vincula_la_cuenta_y_conserva_el_rol`.
4. **`CODIGO_COORDINACION` sin configurar en el servidor:** nadie se vuelve coordinador, ni con código vacío ni con uno cualquiera. Tarea 4, `test_sin_codigo_configurado_nadie_es_coordinador` y la tabla de `test_es_codigo_de_coordinacion`.
5. **Alerta sin umbral:** se rechaza; si no, dos alertas sin umbral pasarían el índice único y se duplicarían avisos. Tarea 1, `test_alerta_sin_umbral_es_rechazada`.

---

## Estructura de archivos

```
backend/
  pyproject.toml                                   (T2)  + pyjwt[crypto]
  .env.example                                     (T2)  SUPABASE_URL, SUPABASE_JWT_SECRET, CODIGO_COORDINACION
  CLAUDE.md                                        (T5, T6)
  migrations/versions/0002_operacion_y_bitacora.py (T1)
  app/config.py                                    (T2)  supabase_url, supabase_jwt_secret, codigo_coordinacion
  app/auth.py                                      (T2, T3)  Identidad, VerificadorToken, get_verificador, identidad_actual,
                                                           usuario_registrado, usuario_actual, requiere_coordinador
  app/main.py                                      (T3)  registra el router de sesión
  app/api/esquemas.py                              (T3)  Esquema (base camelCase compartida)
  app/api/turnos.py                                (T3)  usa Esquema y exige usuario_actual
  app/api/sesion.py                                (T3, T4)  GET /me, POST /registro
  app/dominio/registro.py                          (T4)  es_codigo_de_coordinacion
  app/modelos/__init__.py                          (T1)
  app/modelos/horario.py                           (T1)  + UniqueConstraint (id, horario_id)
  app/modelos/turno.py                             (T1)  Turno, Vacante, EstadoVacante, Postulacion
  app/modelos/evento.py                            (T1)  EventoTurno, TipoEventoTurno
  app/modelos/notificacion.py                      (T1)  Notificacion
  app/repos/usuarios.py                            (T3, T4)  buscar_por_auth_id, buscar_por_email
  tests/conftest.py                                (T2)  el cliente usa el verificador de prueba
  tests/fabricas.py                                (T1, T2)  guardar, debe_fallar, token_para, encabezados
  tests/test_modelo.py                             (T1)  importa guardar y debe_fallar de fabricas
  tests/test_modelo_operacion.py                   (T1)
  scripts/seed.py                                  (T6)  conserva auth_id por email al recargar
  tests/test_seed.py                               (T1, T6)
  tests/test_auth.py                               (T2)
  tests/test_api_sesion.py                         (T3)
  tests/test_permisos.py                           (T3)
  tests/test_api_turnos.py                         (T3)  pedidos con sesión
  tests/test_registro.py                           (T4)
  tests/test_api_registro.py                       (T4)
CLAUDE.md, docs/plan-de-implementacion.md, docs/prompts-principales.md   (T5)
```

Orden de las tareas: el modelo va primero para que el integrante que hace vacantes y postulaciones pueda partir de esta branch apenas se mergee la tarea 1, sin esperar la autenticación.

---

### Tarea 1: migración 0002 y modelos Turno, Vacante, Postulacion, EventoTurno y Notificacion

**Archivos:**
- Crear: `backend/migrations/versions/0002_operacion_y_bitacora.py`
- Crear: `backend/app/modelos/turno.py`, `backend/app/modelos/evento.py`, `backend/app/modelos/notificacion.py`
- Modificar: `backend/app/modelos/horario.py`, `backend/app/modelos/__init__.py`
- Modificar: `backend/tests/fabricas.py`, `backend/tests/test_modelo.py`, `backend/tests/test_seed.py`
- Crear: `backend/tests/test_modelo_operacion.py`

**Interfaces:**
- Consume: `HorarioPactado`, `VersionHorario`, `Usuario` (F1); `crear_horario(sesion, datos: DatosVersion, vigente_desde) -> HorarioPactado` de `app/repos/horarios.py`.
- Produce (exportado desde `app.modelos`): `Turno`, `Vacante`, `EstadoVacante`, `Postulacion`, `EventoTurno`, `TipoEventoTurno`, `Notificacion`. En `tests/fabricas.py`: `guardar(sesion, objeto)` y `debe_fallar(sesion, objeto, restriccion: str)`.

- [ ] **Paso 1: mover `guardar` y `debe_fallar` a `tests/fabricas.py`**

Agregar al final de `backend/tests/fabricas.py` (y los imports `import pytest` y `from sqlalchemy.exc import IntegrityError` arriba):

```python
def guardar(sesion: Session, objeto) -> None:
    sesion.add(objeto)
    sesion.flush()


def debe_fallar(sesion: Session, objeto, restriccion: str) -> None:
    """Verifica que guardar el objeto viola exactamente la restricción indicada, sin romper la sesión."""
    with pytest.raises(IntegrityError) as excinfo:
        with sesion.begin_nested():
            guardar(sesion, objeto)
    assert excinfo.value.orig.diag.constraint_name == restriccion
```

En `backend/tests/test_modelo.py`, borrar las definiciones locales de `guardar` y `debe_fallar`, y cambiar el import a `from fabricas import crear_usuario, debe_fallar, guardar`. Quitar `IntegrityError` del import de `sqlalchemy.exc` si ya no se usa en el archivo.

Run: `.venv/bin/pytest tests/test_modelo.py -q`
Expected: todas pasan (el cambio es solo de lugar).

- [ ] **Paso 2: escribir las pruebas que fallan**

Crear `backend/tests/test_modelo_operacion.py`:

```python
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.modelos import (
    EstadoVacante,
    EventoTurno,
    Notificacion,
    Postulacion,
    TipoEventoTurno,
    Turno,
    Vacante,
    VersionHorario,
)
from app.repos.horarios import DatosVersion, crear_horario
from fabricas import crear_usuario, debe_fallar, guardar

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
SABADO = date(2026, 10, 17)
INICIO = datetime(2026, 10, 17, 8, tzinfo=ZONA)
FIN = datetime(2026, 10, 17, 20, tzinfo=ZONA)
AHORA = datetime(2026, 10, 12, 9, tzinfo=ZONA)


def nuevo_horario(sesion, medico):
    datos = DatosVersion(
        medico_id=medico.id,
        dia_semana=6,
        hora_inicio=time(8),
        duracion_horas=12,
        frecuencia_semanas=1,
        fecha_ancla=date(2026, 9, 7),
    )
    horario = crear_horario(sesion, datos, date(2026, 9, 7))
    version_id = sesion.scalar(select(VersionHorario.id).where(VersionHorario.horario_id == horario.id))
    return horario, version_id


def fila_turno(horario_id, version_id, titular_id, **cambios) -> Turno:
    datos = dict(
        horario_id=horario_id, fecha=SABADO, version_id=version_id, inicio=INICIO, fin=FIN, titular_id=titular_id
    )
    datos.update(cambios)
    return Turno(**datos)


def fila_vacante(turno, autor, **cambios) -> Vacante:
    datos = dict(turno_id=turno.id, generada_por_id=autor.id, motivo="Congreso", creada_en=AHORA)
    datos.update(cambios)
    return Vacante(**datos)


def fila_evento(turno, tipo=TipoEventoTurno.VACANTE_GENERADA, **cambios) -> EventoTurno:
    datos = dict(turno_id=turno.id, tipo=tipo, actor_id=None, ocurrido_en=AHORA)
    datos.update(cambios)
    return EventoTurno(**datos)


@pytest.fixture
def medico(sesion):
    return crear_usuario(sesion, "Florencia Lucca")


@pytest.fixture
def turno(sesion, medico):
    horario, version_id = nuevo_horario(sesion, medico)
    fila = fila_turno(horario.id, version_id, medico.id)
    guardar(sesion, fila)
    return fila


def test_migracion_crea_las_tablas_operativas_con_rls(sesion):
    filas = sesion.execute(
        text(
            "SELECT relname, relrowsecurity FROM pg_class WHERE relname IN "
            "('turno', 'vacante', 'postulacion', 'evento_turno', 'notificacion') ORDER BY relname"
        )
    ).all()
    assert filas == [
        ("evento_turno", True),
        ("notificacion", True),
        ("postulacion", True),
        ("turno", True),
        ("vacante", True),
    ]


def test_turno_guarda_el_snapshot_con_zona_horaria(sesion, turno, medico):
    sesion.expire_all()
    leido = sesion.get(Turno, turno.id)
    assert leido.inicio == INICIO
    assert leido.inicio.utcoffset() is not None
    assert leido.titular_id == medico.id
    assert (leido.asignado_id, leido.realizador_id, leido.consolidado_en, leido.sin_cobertura_en) == (
        None,
        None,
        None,
        None,
    )


def test_turno_unico_por_horario_y_fecha(sesion, turno):
    debe_fallar(sesion, fila_turno(turno.horario_id, turno.version_id, None), "ux_turno_horario_fecha")


def test_turno_rechaza_la_version_de_otro_horario(sesion, turno, medico):
    _, version_ajena = nuevo_horario(sesion, medico)
    fila = fila_turno(turno.horario_id, version_ajena, medico.id, fecha=date(2026, 10, 24))
    debe_fallar(sesion, fila, "fk_turno_version_del_horario")


def test_turno_rechaza_fin_que_no_es_posterior_al_inicio(sesion, turno):
    fila = fila_turno(turno.horario_id, turno.version_id, None, fecha=date(2026, 10, 24), fin=INICIO)
    debe_fallar(sesion, fila, "ck_turno_fin_posterior")


def test_realizador_solo_en_turno_consolidado(sesion, turno, medico):
    sin_consolidar = fila_turno(turno.horario_id, turno.version_id, None, fecha=date(2026, 10, 24), realizador_id=medico.id)
    debe_fallar(sesion, sin_consolidar, "ck_turno_realizador_consolidado")
    consolidado = fila_turno(
        turno.horario_id, turno.version_id, None, fecha=date(2026, 10, 31), realizador_id=medico.id, consolidado_en=FIN
    )
    guardar(sesion, consolidado)


def test_vacante_nace_abierta(sesion, turno, medico):
    vacante = fila_vacante(turno, medico)
    guardar(sesion, vacante)
    sesion.refresh(vacante)
    assert vacante.estado == EstadoVacante.ABIERTA
    assert vacante.cerrada_en is None


def test_una_sola_vacante_abierta_por_turno(sesion, turno, medico):
    guardar(sesion, fila_vacante(turno, medico))
    debe_fallar(sesion, fila_vacante(turno, medico), "ux_vacante_abierta_por_turno")


def test_se_abre_otra_vacante_cuando_las_anteriores_se_cerraron(sesion, turno, medico):
    guardar(sesion, fila_vacante(turno, medico, estado=EstadoVacante.RETIRADA, cerrada_en=AHORA))
    guardar(sesion, fila_vacante(turno, medico, estado=EstadoVacante.CUBIERTA, cerrada_en=AHORA))
    guardar(sesion, fila_vacante(turno, medico))


@pytest.mark.parametrize(
    "cambios",
    [
        dict(estado=EstadoVacante.ABIERTA, cerrada_en=AHORA),
        dict(estado=EstadoVacante.RETIRADA, cerrada_en=None),
        dict(estado=EstadoVacante.SIN_COBERTURA, cerrada_en=None),
    ],
)
def test_vacante_cerrada_si_y_solo_si_tiene_fecha_de_cierre(sesion, turno, medico, cambios):
    debe_fallar(sesion, fila_vacante(turno, medico, **cambios), "ck_vacante_cierre")


def test_postulacion_unica_por_turno_y_medico(sesion, turno):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    guardar(sesion, Postulacion(turno_id=turno.id, medico_id=carlos.id, creada_en=AHORA))
    debe_fallar(
        sesion, Postulacion(turno_id=turno.id, medico_id=carlos.id, creada_en=AHORA), "ux_postulacion_turno_medico"
    )


def test_evento_de_sistema_con_datos_vacios(sesion, turno):
    evento = fila_evento(turno)
    guardar(sesion, evento)
    sesion.refresh(evento)
    assert evento.actor_id is None
    assert evento.datos == {}


@pytest.mark.parametrize(
    "sentencia",
    ["UPDATE evento_turno SET actor_id = NULL WHERE id = :id", "DELETE FROM evento_turno WHERE id = :id"],
)
def test_bitacora_solo_admite_agregar(sesion, turno, medico, sentencia):
    evento = fila_evento(turno, actor_id=medico.id)
    guardar(sesion, evento)
    with pytest.raises(IntegrityError, match="solo admite agregar"):
        with sesion.begin_nested():
            sesion.execute(text(sentencia), {"id": evento.id})


def test_alerta_sin_cobertura_una_sola_vez_por_umbral(sesion, turno):
    alerta = TipoEventoTurno.ALERTA_SIN_COBERTURA
    guardar(sesion, fila_evento(turno, alerta, datos={"umbral": "48H"}))
    guardar(sesion, fila_evento(turno, alerta, datos={"umbral": "24H"}))
    debe_fallar(sesion, fila_evento(turno, alerta, datos={"umbral": "48H"}), "ux_evento_alerta_por_umbral")


def test_alerta_sin_umbral_es_rechazada(sesion, turno):
    debe_fallar(sesion, fila_evento(turno, TipoEventoTurno.ALERTA_SIN_COBERTURA), "ck_evento_alerta_umbral")


def test_otros_eventos_se_repiten_sin_limite(sesion, turno):
    guardar(sesion, fila_evento(turno, TipoEventoTurno.POSTULACION_CREADA))
    guardar(sesion, fila_evento(turno, TipoEventoTurno.POSTULACION_CREADA))


def test_notificacion_nace_sin_leer(sesion, turno, medico):
    notificacion = Notificacion(
        usuario_id=medico.id,
        tipo="VACANTE_URGENTE",
        mensaje="Vacante urgente el sábado 17/10 a las 08:00",
        turno_id=turno.id,
        creada_en=AHORA,
    )
    guardar(sesion, notificacion)
    sesion.refresh(notificacion)
    assert notificacion.leida_en is None
    assert notificacion.datos == {}
```

Agregar al final de `backend/tests/test_seed.py` (y sumar `datetime`, `Turno`, `Vacante`, `Postulacion`, `EventoTurno`, `Notificacion`, `TipoEventoTurno` a los imports):

```python
def test_seed_vacia_las_tablas_operativas(sesion):
    cargar_datos_ejemplo(sesion)
    medico = sesion.scalars(select(Usuario).order_by(Usuario.id)).first()
    version = sesion.scalars(select(VersionHorario).order_by(VersionHorario.id)).first()
    turno = Turno(
        horario_id=version.horario_id,
        fecha=date(2026, 10, 17),
        version_id=version.id,
        inicio=datetime(2026, 10, 17, 8, tzinfo=ZONA),
        fin=datetime(2026, 10, 17, 20, tzinfo=ZONA),
        titular_id=medico.id,
    )
    sesion.add(turno)
    sesion.flush()
    ahora = datetime(2026, 10, 12, 9, tzinfo=ZONA)
    sesion.add_all(
        [
            Vacante(turno_id=turno.id, generada_por_id=medico.id, creada_en=ahora),
            Postulacion(turno_id=turno.id, medico_id=medico.id, creada_en=ahora),
            EventoTurno(turno_id=turno.id, tipo=TipoEventoTurno.VACANTE_GENERADA, ocurrido_en=ahora),
            Notificacion(usuario_id=medico.id, tipo="PRUEBA", mensaje="x", creada_en=ahora),
        ]
    )
    sesion.flush()
    # La recarga reutiliza los ids (RESTART IDENTITY): soltar los objetos de la carga anterior.
    # Desde la tarea 6, el seed lo hace por su cuenta.
    sesion.expunge_all()

    cargar_datos_ejemplo(sesion)

    for modelo in (Turno, Vacante, Postulacion, EventoTurno, Notificacion):
        assert contar(sesion, modelo) == 0
```

- [ ] **Paso 3: correr y ver que fallan**

Run: `.venv/bin/pytest tests/test_modelo_operacion.py tests/test_seed.py -q`
Expected: FAIL con `ImportError: cannot import name 'EstadoVacante' from 'app.modelos'`.

- [ ] **Paso 4: escribir la migración**

Crear `backend/migrations/versions/0002_operacion_y_bitacora.py`:

```python
"""Turno materializado, vacantes, postulaciones, bitácora y notificaciones (D08, D11, D15, D16, D19 a D22, D25, D07)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-07
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_UPGRADE = [
    "CREATE TYPE estado_vacante AS ENUM ('ABIERTA', 'RETIRADA', 'CUBIERTA', 'SIN_COBERTURA')",
    """
    CREATE TYPE tipo_evento_turno AS ENUM (
        'VACANTE_GENERADA', 'VACANTE_RETIRADA', 'POSTULACION_CREADA', 'POSTULACION_RETIRADA',
        'CANDIDATO_ELEGIDO', 'ASIGNACION_DIRECTA', 'REASIGNACION', 'TURNO_SIN_COBERTURA',
        'REALIZADOR_RECTIFICADO', 'ALERTA_SIN_COBERTURA'
    )
    """,
    # Destino de la FK compuesta del turno: la versión tiene que ser del mismo horario.
    "ALTER TABLE version_horario ADD CONSTRAINT ux_version_horario_id_horario UNIQUE (id, horario_id)",
    """
    CREATE TABLE turno (
        id serial PRIMARY KEY,
        horario_id integer NOT NULL REFERENCES horario_pactado (id),
        fecha date NOT NULL,
        version_id integer NOT NULL,
        inicio timestamptz NOT NULL,
        fin timestamptz NOT NULL,
        titular_id integer REFERENCES usuario (id),
        asignado_id integer REFERENCES usuario (id),
        realizador_id integer REFERENCES usuario (id),
        sin_cobertura_en timestamptz,
        consolidado_en timestamptz,
        creado_en timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT ux_turno_horario_fecha UNIQUE (horario_id, fecha),
        CONSTRAINT fk_turno_version_del_horario FOREIGN KEY (version_id, horario_id)
            REFERENCES version_horario (id, horario_id),
        CONSTRAINT ck_turno_fin_posterior CHECK (fin > inicio),
        CONSTRAINT ck_turno_realizador_consolidado CHECK (realizador_id IS NULL OR consolidado_en IS NOT NULL)
    )
    """,
    "CREATE INDEX ix_turno_inicio ON turno (inicio)",
    "CREATE INDEX ix_turno_asignado ON turno (asignado_id)",
    """
    CREATE TABLE vacante (
        id serial PRIMARY KEY,
        turno_id integer NOT NULL REFERENCES turno (id),
        generada_por_id integer NOT NULL REFERENCES usuario (id),
        motivo text,
        estado estado_vacante NOT NULL DEFAULT 'ABIERTA',
        creada_en timestamptz NOT NULL,
        cerrada_en timestamptz,
        CONSTRAINT ck_vacante_cierre CHECK ((estado = 'ABIERTA') = (cerrada_en IS NULL))
    )
    """,
    # D15: como máximo una vacante abierta por turno.
    "CREATE UNIQUE INDEX ux_vacante_abierta_por_turno ON vacante (turno_id) WHERE estado = 'ABIERTA'",
    """
    CREATE TABLE postulacion (
        id serial PRIMARY KEY,
        turno_id integer NOT NULL REFERENCES turno (id),
        medico_id integer NOT NULL REFERENCES usuario (id),
        creada_en timestamptz NOT NULL,
        retirada_en timestamptz,
        CONSTRAINT ux_postulacion_turno_medico UNIQUE (turno_id, medico_id)
    )
    """,
    "CREATE INDEX ix_postulacion_medico ON postulacion (medico_id)",
    """
    CREATE TABLE evento_turno (
        id serial PRIMARY KEY,
        turno_id integer NOT NULL REFERENCES turno (id),
        tipo tipo_evento_turno NOT NULL,
        actor_id integer REFERENCES usuario (id),
        ocurrido_en timestamptz NOT NULL,
        datos jsonb NOT NULL DEFAULT '{}'::jsonb,
        CONSTRAINT ck_evento_alerta_umbral CHECK (tipo <> 'ALERTA_SIN_COBERTURA' OR datos->>'umbral' IS NOT NULL)
    )
    """,
    "CREATE INDEX ix_evento_turno_turno ON evento_turno (turno_id, ocurrido_en)",
    # D19: cada alerta escalonada se emite una sola vez por turno y umbral.
    """
    CREATE UNIQUE INDEX ux_evento_alerta_por_umbral ON evento_turno (turno_id, (datos->>'umbral'))
        WHERE tipo = 'ALERTA_SIN_COBERTURA'
    """,
    # D22: la bitácora solo se agrega. TRUNCATE (seed y pruebas) no dispara triggers de fila.
    """
    CREATE FUNCTION evento_turno_solo_agregar() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION 'La bitácora (evento_turno) solo admite agregar filas' USING ERRCODE = 'restrict_violation';
    END
    $$
    """,
    """
    CREATE TRIGGER tg_evento_turno_solo_agregar BEFORE UPDATE OR DELETE ON evento_turno
        FOR EACH ROW EXECUTE FUNCTION evento_turno_solo_agregar()
    """,
    """
    CREATE TABLE notificacion (
        id serial PRIMARY KEY,
        usuario_id integer NOT NULL REFERENCES usuario (id),
        tipo text NOT NULL,
        mensaje text NOT NULL,
        turno_id integer REFERENCES turno (id),
        datos jsonb NOT NULL DEFAULT '{}'::jsonb,
        creada_en timestamptz NOT NULL,
        leida_en timestamptz
    )
    """,
    "CREATE INDEX ix_notificacion_usuario ON notificacion (usuario_id, creada_en)",
    # D07: RLS activado sin políticas.
    "ALTER TABLE turno ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE vacante ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE postulacion ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE evento_turno ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE notificacion ENABLE ROW LEVEL SECURITY",
]

_DOWNGRADE = [
    "DROP TABLE notificacion",
    "DROP TABLE evento_turno",
    "DROP FUNCTION evento_turno_solo_agregar()",
    "DROP TABLE postulacion",
    "DROP TABLE vacante",
    "DROP TABLE turno",
    "ALTER TABLE version_horario DROP CONSTRAINT ux_version_horario_id_horario",
    "DROP TYPE tipo_evento_turno",
    "DROP TYPE estado_vacante",
]


def upgrade() -> None:
    for sentencia in _UPGRADE:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _DOWNGRADE:
        op.execute(sentencia)
```

- [ ] **Paso 5: escribir los modelos**

En `backend/app/modelos/horario.py`, sumar `UniqueConstraint` al import de `sqlalchemy` y agregar al final de `VersionHorario.__table_args__`:

```python
        UniqueConstraint("id", "horario_id", name="ux_version_horario_id_horario"),
```

Crear `backend/app/modelos/turno.py`:

```python
import enum
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.base import Base


class Turno(Base):
    """Guardia concreta, guardada solo cuando se genera una vacante o al consolidarse (D08, D09, D11).

    inicio, fin, version_id y titular_id son una foto del momento en que se guardó: no se recalculan
    si cambia la plantilla (D11, D12). asignado_id es el asignado actual; los anteriores quedan en la
    bitácora (D08). realizador_id solo existe en un turno consolidado (D20, D21).
    """

    __tablename__ = "turno"
    __table_args__ = (
        UniqueConstraint("horario_id", "fecha", name="ux_turno_horario_fecha"),
        ForeignKeyConstraint(
            ["version_id", "horario_id"],
            ["version_horario.id", "version_horario.horario_id"],
            name="fk_turno_version_del_horario",
        ),
        CheckConstraint("fin > inicio", name="ck_turno_fin_posterior"),
        CheckConstraint(
            "realizador_id IS NULL OR consolidado_en IS NOT NULL", name="ck_turno_realizador_consolidado"
        ),
        Index("ix_turno_inicio", "inicio"),
        Index("ix_turno_asignado", "asignado_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    horario_id: Mapped[int] = mapped_column(ForeignKey("horario_pactado.id"))
    fecha: Mapped[date]
    version_id: Mapped[int]
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    titular_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    asignado_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    realizador_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    sin_cobertura_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consolidado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EstadoVacante(str, enum.Enum):
    ABIERTA = "ABIERTA"
    RETIRADA = "RETIRADA"
    CUBIERTA = "CUBIERTA"
    SIN_COBERTURA = "SIN_COBERTURA"


class Vacante(Base):
    """Aviso de ausencia sobre un turno (D15). Como máximo una abierta por turno.

    motivo es visible solo para coordinadores (D25): la API lo filtra según el rol.
    urgente no se guarda: se calcula como inicio del turno - creada_en < 24 h.
    creada_en y cerrada_en los completa la aplicación con el reloj inyectable (D27).
    """

    __tablename__ = "vacante"
    __table_args__ = (
        CheckConstraint("(estado = 'ABIERTA') = (cerrada_en IS NULL)", name="ck_vacante_cierre"),
        Index(
            "ux_vacante_abierta_por_turno", "turno_id", unique=True, postgresql_where=text("estado = 'ABIERTA'")
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    turno_id: Mapped[int] = mapped_column(ForeignKey("turno.id"))
    generada_por_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    motivo: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[EstadoVacante] = mapped_column(
        Enum(EstadoVacante, name="estado_vacante"), server_default=EstadoVacante.ABIERTA.value
    )
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cerrada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Postulacion(Base):
    """Oferta de un médico para cubrir un turno, no una vacante (D16).

    Única por (turno, médico) aunque esté retirada: volver a postularse reactiva la misma fila.
    creada_en es la hora del servidor que desempata el orden de candidatos (D17).
    """

    __tablename__ = "postulacion"
    __table_args__ = (
        UniqueConstraint("turno_id", "medico_id", name="ux_postulacion_turno_medico"),
        Index("ix_postulacion_medico", "medico_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    turno_id: Mapped[int] = mapped_column(ForeignKey("turno.id"))
    medico_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retirada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Crear `backend/app/modelos/evento.py`:

```python
import enum
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.base import Base


class TipoEventoTurno(str, enum.Enum):
    VACANTE_GENERADA = "VACANTE_GENERADA"
    VACANTE_RETIRADA = "VACANTE_RETIRADA"
    POSTULACION_CREADA = "POSTULACION_CREADA"
    POSTULACION_RETIRADA = "POSTULACION_RETIRADA"
    CANDIDATO_ELEGIDO = "CANDIDATO_ELEGIDO"
    ASIGNACION_DIRECTA = "ASIGNACION_DIRECTA"
    REASIGNACION = "REASIGNACION"
    TURNO_SIN_COBERTURA = "TURNO_SIN_COBERTURA"
    REALIZADOR_RECTIFICADO = "REALIZADOR_RECTIFICADO"
    ALERTA_SIN_COBERTURA = "ALERTA_SIN_COBERTURA"


class EventoTurno(Base):
    """Bitácora de acciones sobre un turno (D22). Solo se agrega: un trigger rechaza UPDATE y DELETE.

    Se escribe en la misma transacción que la acción. actor_id vacío = acción del sistema.
    datos guarda solo lo que ninguna entidad conserva: posición y cantidad de candidatos,
    valor anterior, motivo de la rectificación, umbral de la alerta ("48H", "24H" o "INICIO").
    """

    __tablename__ = "evento_turno"
    __table_args__ = (
        CheckConstraint(
            "tipo <> 'ALERTA_SIN_COBERTURA' OR datos->>'umbral' IS NOT NULL", name="ck_evento_alerta_umbral"
        ),
        Index("ix_evento_turno_turno", "turno_id", "ocurrido_en"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    turno_id: Mapped[int] = mapped_column(ForeignKey("turno.id"))
    tipo: Mapped[TipoEventoTurno] = mapped_column(Enum(TipoEventoTurno, name="tipo_evento_turno"))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    ocurrido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    datos: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))


Index(
    "ux_evento_alerta_por_umbral",
    EventoTurno.turno_id,
    EventoTurno.datos["umbral"].astext,
    unique=True,
    postgresql_where=EventoTurno.tipo == TipoEventoTurno.ALERTA_SIN_COBERTURA,
)
```

Crear `backend/app/modelos/notificacion.py`:

```python
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.base import Base


class Notificacion(Base):
    """Aviso dentro de la app para un usuario (D05). Se escribe en la misma transacción que la acción (D22).

    tipo es texto en MAYÚSCULAS (por ejemplo VACANTE_URGENTE); la lista la fija F4 sin cambiar el esquema.
    """

    __tablename__ = "notificacion"
    __table_args__ = (Index("ix_notificacion_usuario", "usuario_id", "creada_en"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    tipo: Mapped[str] = mapped_column(Text)
    mensaje: Mapped[str] = mapped_column(Text)
    turno_id: Mapped[int | None] = mapped_column(ForeignKey("turno.id"))
    datos: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    leida_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Reemplazar `backend/app/modelos/__init__.py`:

```python
from app.modelos.base import Base
from app.modelos.evento import EventoTurno, TipoEventoTurno
from app.modelos.horario import HorarioPactado, VersionHorario
from app.modelos.notificacion import Notificacion
from app.modelos.turno import EstadoVacante, Postulacion, Turno, Vacante
from app.modelos.usuario import EstadoUsuario, RolUsuario, Usuario

__all__ = [
    "Base",
    "EstadoUsuario",
    "EstadoVacante",
    "EventoTurno",
    "HorarioPactado",
    "Notificacion",
    "Postulacion",
    "RolUsuario",
    "TipoEventoTurno",
    "Turno",
    "Usuario",
    "Vacante",
    "VersionHorario",
]
```

- [ ] **Paso 6: correr y ver que pasan**

Run: `.venv/bin/pytest tests/test_modelo_operacion.py tests/test_seed.py tests/test_modelo.py -q`
Expected: todas pasan.

- [ ] **Paso 7: verificar que la migración baja y sube (contra la base local, nunca Supabase)**

Run: `DATABASE_URL=postgresql://guardia:guardia@localhost:5433/guardia .venv/bin/alembic upgrade head && DATABASE_URL=postgresql://guardia:guardia@localhost:5433/guardia .venv/bin/alembic downgrade 0001 && DATABASE_URL=postgresql://guardia:guardia@localhost:5433/guardia .venv/bin/alembic upgrade head`
Expected: los tres comandos terminan sin error.

- [ ] **Paso 8: suite completa y commit**

Run: `.venv/bin/pytest -q`
Expected: todas pasan.

```bash
git add backend/migrations/versions/0002_operacion_y_bitacora.py backend/app/modelos backend/tests/fabricas.py backend/tests/test_modelo.py backend/tests/test_modelo_operacion.py backend/tests/test_seed.py
git commit -m "$(cat <<'EOF'
Modelo operativo: turno, vacante, postulación, bitácora y notificación (D08, D11, D15, D16, D19, D22, D25)

Migración 0002 con turno único por (horario, fecha), una vacante abierta por turno,
postulación única por (turno, médico), bitácora solo de agregar (trigger), alerta única
por umbral y RLS en las tablas nuevas.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarea 2: verificación del token de Supabase Auth

**Archivos:**
- Modificar: `backend/pyproject.toml`, `backend/.env.example`, `backend/app/config.py`, `backend/app/auth.py`
- Modificar: `backend/tests/fabricas.py`, `backend/tests/conftest.py`
- Crear: `backend/tests/test_auth.py`

**Interfaces:**
- Consume: `ErrorDominio(codigo, mensaje, status)` de `app/errores.py`; `registrar_manejadores(app)` de `app/api/manejadores.py`.
- Produce, en `app/auth.py`: `Identidad(auth_id: uuid.UUID, email: str | None)`; `VerificadorToken(secreto: str | None = None, jwks: FuenteDeClaves | None = None)` con `.verificar(token: str) -> Identidad`; `get_verificador() -> VerificadorToken` (dependencia); `identidad_actual(...) -> Identidad` (dependencia). En `tests/fabricas.py`: `SECRETO_PRUEBA`, `token_para(auth_id, email=..., vence_en=..., clave=..., algoritmo=..., **claims) -> str`, `encabezados(usuario) -> dict[str, str]`. La fixture `cliente` usa `VerificadorToken(secreto=SECRETO_PRUEBA)`.
- Se conserva temporalmente `usuario_actual()` (enganche de F1, devuelve `None`) hasta la tarea 3.

- [ ] **Paso 1: dependencia y configuración**

En `backend/pyproject.toml`, agregar a `dependencies`:

```toml
  "pyjwt[crypto]>=2.9",
```

Run: `.venv/bin/pip install -e ".[dev]"`
Expected: instala `PyJWT` y `cryptography`.

En `backend/app/config.py`, agregar a `Settings` (después de `modo_demo`):

```python
    # D06: verificación de tokens de Supabase Auth. Con SUPABASE_URL se usan las claves públicas (JWKS) del
    # proyecto; con SUPABASE_JWT_SECRET, el secreto HS256 de los proyectos anteriores. Puede haber ambos.
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    # D30: código de coordinación del servicio. Vacío = nadie puede registrarse como coordinador.
    codigo_coordinacion: str = ""
```

Agregar al final de `backend/.env.example`:

```
# Supabase Auth (D06). URL del proyecto (Project Settings > API) para verificar tokens con las claves públicas.
SUPABASE_URL=
# Solo si el proyecto todavía firma con el secreto JWT (Project Settings > API > JWT Settings).
SUPABASE_JWT_SECRET=
# Código de coordinación del servicio (D30). Nunca se versiona su valor real.
CODIGO_COORDINACION=
```

- [ ] **Paso 2: ayudas de prueba para tokens**

En `backend/tests/fabricas.py`, sumar los imports `import time`, `import uuid`, `from datetime import timedelta` e `import jwt`, y:

1. Agregar el parámetro `con_cuenta: bool = True` a `crear_usuario` y pasar `auth_id=uuid.uuid4() if con_cuenta else None` al construir el `Usuario` (los usuarios de prueba tienen cuenta de Supabase salvo que se pida lo contrario, como los que carga el seed).
2. Agregar al final:

```python
SECRETO_PRUEBA = "secreto-de-prueba-de-guardia-viva-de-32-bytes-o-mas"


def token_para(
    auth_id,
    email: str | None = "medico@prueba.test",
    vence_en: timedelta = timedelta(hours=1),
    clave=SECRETO_PRUEBA,
    algoritmo: str = "HS256",
    **claims,
) -> str:
    """Token de acceso como los de Supabase Auth. Un claim en None se omite.

    Usa la hora real: PyJWT controla el vencimiento con ella (ver "Decisiones de este plan" en el plan de F2).
    """
    ahora = int(time.time())
    carga = {
        "sub": str(auth_id),
        "email": email,
        "aud": "authenticated",
        "role": "authenticated",
        "iat": ahora,
        "exp": ahora + int(vence_en.total_seconds()),
    }
    carga.update(claims)
    return jwt.encode({k: v for k, v in carga.items() if v is not None}, clave, algorithm=algoritmo)


def encabezados(usuario) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_para(usuario.auth_id, email=usuario.email)}"}
```

- [ ] **Paso 3: escribir las pruebas que fallan**

Crear `backend/tests/test_auth.py`:

```python
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.manejadores import registrar_manejadores
from app.auth import Identidad, VerificadorToken, _cliente_jwks, get_verificador, identidad_actual
from app.config import get_settings
from app.errores import ErrorDominio
from fabricas import SECRETO_PRUEBA, token_para

AUTH_ID = uuid.UUID("2b6f0c1e-8a54-4a43-9a51-6f1c1f0d9e11")
CLAVE_EC = ec.generate_private_key(ec.SECP256R1())


class ClavesFijas:
    """Reemplaza al cliente JWKS de Supabase: siempre devuelve la misma clave pública."""

    def __init__(self, clave_publica) -> None:
        self._clave = clave_publica

    def get_signing_key_from_jwt(self, _token: str):
        return SimpleNamespace(key=self._clave)


def con_secreto() -> VerificadorToken:
    return VerificadorToken(secreto=SECRETO_PRUEBA)


def con_jwks() -> VerificadorToken:
    return VerificadorToken(jwks=ClavesFijas(CLAVE_EC.public_key()))


def error_de(verificador: VerificadorToken, token: str) -> ErrorDominio:
    with pytest.raises(ErrorDominio) as excinfo:
        verificador.verificar(token)
    return excinfo.value


def test_token_hs256_valido_devuelve_la_identidad():
    identidad = con_secreto().verificar(token_para(AUTH_ID, email="florencia@prueba.test"))
    assert identidad == Identidad(auth_id=AUTH_ID, email="florencia@prueba.test")


def test_token_es256_se_verifica_con_la_clave_publica():
    token = token_para(AUTH_ID, clave=CLAVE_EC, algoritmo="ES256")
    assert con_jwks().verificar(token).auth_id == AUTH_ID


def test_token_sin_email_da_identidad_sin_email():
    assert con_secreto().verificar(token_para(AUTH_ID, email=None)).email is None


def test_token_vencido():
    error = error_de(con_secreto(), token_para(AUTH_ID, vence_en=timedelta(seconds=-30)))
    assert (error.codigo, error.status) == ("TOKEN_VENCIDO", 401)


@pytest.mark.parametrize(
    "token",
    [
        "no-es-un-jwt",
        token_para(AUTH_ID, clave="otro-secreto-que-tambien-tiene-32-bytes-o-mas"),
        token_para(AUTH_ID, clave=None, algoritmo="none"),
        token_para(AUTH_ID, aud="otra-audiencia"),
        token_para(AUTH_ID, aud=None),
        token_para(AUTH_ID, sub=None),
        token_para(AUTH_ID, sub="no-es-un-uuid"),
        token_para(AUTH_ID, exp=None),
        token_para(AUTH_ID, clave=CLAVE_EC, algoritmo="ES256"),
    ],
    ids=["basura", "otra-clave", "sin-firma", "otra-audiencia", "sin-audiencia", "sin-sub", "sub-no-uuid", "sin-exp", "es256-sin-jwks"],
)
def test_tokens_invalidos(token):
    error = error_de(con_secreto(), token)
    assert (error.codigo, error.status) == ("TOKEN_INVALIDO", 401)


def test_token_hs256_con_verificador_solo_jwks_es_invalido():
    error = error_de(con_jwks(), token_para(AUTH_ID))
    assert error.codigo == "TOKEN_INVALIDO"


def test_sin_configuracion_de_supabase_responde_503(monkeypatch):
    monkeypatch.setattr(get_settings(), "supabase_url", "")
    monkeypatch.setattr(get_settings(), "supabase_jwt_secret", "")
    with pytest.raises(ErrorDominio) as excinfo:
        get_verificador()
    assert (excinfo.value.codigo, excinfo.value.status) == ("AUTH_NO_CONFIGURADA", 503)


def test_las_claves_publicas_salen_de_la_url_del_proyecto():
    assert _cliente_jwks("https://abc.supabase.co/").uri == "https://abc.supabase.co/auth/v1/.well-known/jwks.json"


@pytest.fixture
def cliente_identidad() -> TestClient:
    app = FastAPI()
    registrar_manejadores(app)

    @app.get("/quien")
    def quien(identidad: Identidad = Depends(identidad_actual)) -> dict[str, str]:
        return {"authId": str(identidad.auth_id)}

    app.dependency_overrides[get_verificador] = con_secreto
    return TestClient(app)


def test_bearer_valido_llega_al_endpoint(cliente_identidad):
    r = cliente_identidad.get("/quien", headers={"Authorization": f"Bearer {token_para(AUTH_ID)}"})
    assert r.status_code == 200
    assert r.json() == {"authId": str(AUTH_ID)}


@pytest.mark.parametrize("encabezados", [{}, {"Authorization": "Basic dXN1YXJpbzpjbGF2ZQ=="}, {"Authorization": "Bearer"}])
def test_sin_bearer_es_sin_sesion(cliente_identidad, encabezados):
    r = cliente_identidad.get("/quien", headers=encabezados)
    assert r.status_code == 401
    assert r.json()["codigo"] == "SIN_SESION"


def test_bearer_vencido_responde_token_vencido(cliente_identidad):
    token = token_para(AUTH_ID, vence_en=timedelta(seconds=-30))
    r = cliente_identidad.get("/quien", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json() == {"codigo": "TOKEN_VENCIDO", "mensaje": "La sesión venció. Volvé a ingresar."}
```

- [ ] **Paso 4: correr y ver que fallan**

Run: `.venv/bin/pytest tests/test_auth.py -q`
Expected: FAIL con `ImportError: cannot import name 'Identidad' from 'app.auth'`.

- [ ] **Paso 5: implementar `app/auth.py`**

Reemplazar `backend/app/auth.py`:

```python
"""Autenticación con Supabase Auth (D06).

El frontend inicia sesión contra Supabase Auth y manda el token de acceso en Authorization: Bearer.
El backend solo verifica el token: nunca ve ni guarda contraseñas.
"""

import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.errores import ErrorDominio

AUDIENCIA = "authenticated"
ALGORITMOS_CON_SECRETO = ("HS256",)
ALGORITMOS_CON_CLAVE_PUBLICA = ("ES256", "RS256")


@dataclass(frozen=True)
class Identidad:
    """Lo que el token garantiza sobre quien llama: su cuenta de Supabase Auth y su email."""

    auth_id: uuid.UUID
    email: str | None


class FuenteDeClaves(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> Any: ...


def _token_invalido() -> ErrorDominio:
    return ErrorDominio("TOKEN_INVALIDO", "El token de sesión no es válido.", 401)


class VerificadorToken:
    """Verifica firma, audiencia y vencimiento de un token de acceso de Supabase Auth.

    La clave depende del algoritmo del token: el secreto para HS256, las claves públicas (JWKS) del
    proyecto para ES256 y RS256. Cualquier otro algoritmo, incluido "none", se rechaza.
    El vencimiento lo controla PyJWT con la hora real, no con el reloj inyectable: Supabase emite el
    token en tiempo real, y adelantar el reloj de demo (D27) no debe cerrar las sesiones.
    """

    def __init__(self, secreto: str | None = None, jwks: FuenteDeClaves | None = None) -> None:
        self._secreto = secreto
        self._jwks = jwks

    def verificar(self, token: str) -> Identidad:
        try:
            algoritmo = jwt.get_unverified_header(token).get("alg")
            claims = jwt.decode(
                token,
                self._clave(token, algoritmo),
                algorithms=[algoritmo],
                audience=AUDIENCIA,
                options={"require": ["exp", "sub", "aud"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise ErrorDominio("TOKEN_VENCIDO", "La sesión venció. Volvé a ingresar.", 401) from exc
        except jwt.PyJWKClientConnectionError as exc:
            raise ErrorDominio(
                "AUTH_NO_DISPONIBLE", "No se pudo consultar Supabase Auth para verificar la sesión.", 503
            ) from exc
        except jwt.PyJWTError as exc:
            raise _token_invalido() from exc
        try:
            auth_id = uuid.UUID(claims["sub"])
        except (ValueError, TypeError, AttributeError) as exc:
            raise _token_invalido() from exc
        email = claims.get("email")
        return Identidad(auth_id=auth_id, email=email if isinstance(email, str) and email else None)

    def _clave(self, token: str, algoritmo: str | None) -> Any:
        if algoritmo in ALGORITMOS_CON_SECRETO and self._secreto:
            return self._secreto
        if algoritmo in ALGORITMOS_CON_CLAVE_PUBLICA and self._jwks is not None:
            return self._jwks.get_signing_key_from_jwt(token).key
        raise jwt.InvalidAlgorithmError(f"Algoritmo no aceptado: {algoritmo}")


@lru_cache
def _cliente_jwks(supabase_url: str) -> jwt.PyJWKClient:
    """Un cliente por proyecto: guarda en memoria las claves públicas y las renueva solo si aparece una nueva."""
    return jwt.PyJWKClient(f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json")


def get_verificador() -> VerificadorToken:
    settings = get_settings()
    if not (settings.supabase_url or settings.supabase_jwt_secret):
        raise ErrorDominio(
            "AUTH_NO_CONFIGURADA", "Falta configurar SUPABASE_URL o SUPABASE_JWT_SECRET en el servidor.", 503
        )
    jwks = _cliente_jwks(settings.supabase_url) if settings.supabase_url else None
    return VerificadorToken(secreto=settings.supabase_jwt_secret or None, jwks=jwks)


_bearer = HTTPBearer(auto_error=False)


def identidad_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
    verificador: VerificadorToken = Depends(get_verificador),
) -> Identidad:
    if credenciales is None or not credenciales.credentials:
        raise ErrorDominio("SIN_SESION", "Falta el token de sesión.", 401)
    return verificador.verificar(credenciales.credentials)


def usuario_actual() -> None:
    """Enganche de F1, todavía sin uso de la sesión. La tarea 3 lo reemplaza por el Usuario activo."""
    return None
```

- [ ] **Paso 6: el cliente de pruebas usa el verificador de prueba**

En `backend/tests/conftest.py`, sumar los imports `from app.auth import VerificadorToken, get_verificador` y `from fabricas import SECRETO_PRUEBA`. En la fixture `cliente`, junto a `app.dependency_overrides[get_db] = _get_db`, agregar:

```python
    app.dependency_overrides[get_verificador] = lambda: VerificadorToken(secreto=SECRETO_PRUEBA)
```

y junto a `app.dependency_overrides.pop(get_db, None)`:

```python
    app.dependency_overrides.pop(get_verificador, None)
```

- [ ] **Paso 7: correr y ver que pasan**

Run: `.venv/bin/pytest tests/test_auth.py -q`
Expected: todas pasan.

Run: `.venv/bin/pytest -q`
Expected: toda la suite pasa (incluida `test_sin_hora_del_sistema.py`: `app/auth.py` no consulta la hora).

- [ ] **Paso 8: commit**

```bash
git add backend/pyproject.toml backend/.env.example backend/app/config.py backend/app/auth.py backend/tests/fabricas.py backend/tests/conftest.py backend/tests/test_auth.py
git commit -m "$(cat <<'EOF'
Verificación del token de Supabase Auth (D06)

El backend verifica tokens HS256 con el secreto del proyecto o ES256/RS256 con sus claves
públicas, y rechaza cualquier otro algoritmo. Sin token responde 401 SIN_SESION; con token
vencido, 401 TOKEN_VENCIDO.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarea 3: GET /api/me y permisos por estado y rol

**Archivos:**
- Crear: `backend/app/repos/usuarios.py`, `backend/app/api/esquemas.py`, `backend/app/api/sesion.py`
- Modificar: `backend/app/auth.py`, `backend/app/api/turnos.py`, `backend/app/main.py`
- Modificar: `backend/tests/test_api_turnos.py`
- Crear: `backend/tests/test_api_sesion.py`, `backend/tests/test_permisos.py`

**Interfaces:**
- Consume: `identidad_actual`, `get_verificador`, `VerificadorToken` (tarea 2); `crear_usuario(..., con_cuenta=True)`, `encabezados(usuario)`, `token_para(...)`, `SECRETO_PRUEBA` de `tests/fabricas.py` (tarea 2).
- Produce: `buscar_por_auth_id(sesion, auth_id: uuid.UUID) -> Usuario | None` en `app/repos/usuarios.py`; en `app/auth.py`, las dependencias `usuario_registrado -> Usuario` (cualquier estado), `usuario_actual -> Usuario` (ACTIVO) y `requiere_coordinador -> Usuario` (ACTIVO y COORDINADOR); `Esquema` en `app/api/esquemas.py`; `UsuarioOut` y `router` en `app/api/sesion.py`. El integrante de vacantes y postulaciones usa `usuario_actual` y `requiere_coordinador`.

- [ ] **Paso 1: escribir las pruebas que fallan**

Crear `backend/tests/test_api_sesion.py`:

```python
import uuid

import pytest

from app.modelos import EstadoUsuario, RolUsuario
from fabricas import crear_usuario, encabezados, token_para


def test_me_devuelve_el_usuario_de_la_sesion(cliente, sesion):
    florencia = crear_usuario(sesion, "Florencia Lucca", email="florencia@prueba.test")

    r = cliente.get("/api/me", headers=encabezados(florencia))

    assert r.status_code == 200
    assert r.json() == {
        "id": florencia.id,
        "nombre": "Florencia Lucca",
        "email": "florencia@prueba.test",
        "rol": "MEDICO",
        "estado": "ACTIVO",
    }


@pytest.mark.parametrize("estado", [EstadoUsuario.PENDIENTE, EstadoUsuario.BAJA])
def test_me_responde_tambien_a_cuentas_sin_acceso(cliente, sesion, estado):
    usuario = crear_usuario(sesion, "Ana Pérez", estado=estado)

    r = cliente.get("/api/me", headers=encabezados(usuario))

    assert r.status_code == 200
    assert r.json()["estado"] == estado.value


def test_me_sin_token_es_401(cliente):
    r = cliente.get("/api/me")
    assert r.status_code == 401
    assert r.json()["codigo"] == "SIN_SESION"


def test_me_de_una_cuenta_sin_registro_es_403(cliente):
    r = cliente.get("/api/me", headers={"Authorization": f"Bearer {token_para(uuid.uuid4())}"})
    assert r.status_code == 403
    assert r.json()["codigo"] == "USUARIO_NO_REGISTRADO"


def test_turnos_sin_token_es_401(cliente):
    r = cliente.get("/api/turnos", params={"desde": "2026-10-12", "hasta": "2026-10-18"})
    assert r.status_code == 401
    assert r.json()["codigo"] == "SIN_SESION"


@pytest.mark.parametrize(
    "estado,codigo",
    [(EstadoUsuario.PENDIENTE, "CUENTA_PENDIENTE"), (EstadoUsuario.BAJA, "CUENTA_DADA_DE_BAJA")],
)
def test_turnos_rechaza_cuentas_sin_acceso(cliente, sesion, estado, codigo):
    usuario = crear_usuario(sesion, "Ana Pérez", estado=estado)

    r = cliente.get("/api/turnos", params={"desde": "2026-10-12", "hasta": "2026-10-18"}, headers=encabezados(usuario))

    assert r.status_code == 403
    assert r.json()["codigo"] == codigo


@pytest.mark.parametrize("rol", [RolUsuario.MEDICO, RolUsuario.COORDINADOR])
def test_turnos_acepta_cualquier_rol_activo(cliente, sesion, rol):
    usuario = crear_usuario(sesion, "Activo", rol=rol)

    r = cliente.get("/api/turnos", params={"desde": "2026-10-12", "hasta": "2026-10-18"}, headers=encabezados(usuario))

    assert r.status_code == 200
```

Crear `backend/tests/test_permisos.py`:

```python
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.manejadores import registrar_manejadores
from app.auth import VerificadorToken, get_verificador, requiere_coordinador
from app.db import get_db
from app.modelos import EstadoUsuario, RolUsuario, Usuario
from fabricas import SECRETO_PRUEBA, crear_usuario, encabezados


@pytest.fixture
def cliente_permisos(sesion) -> TestClient:
    app = FastAPI()
    registrar_manejadores(app)

    @app.post("/solo-coordinador")
    def accion(usuario: Usuario = Depends(requiere_coordinador)) -> dict[str, int]:
        return {"id": usuario.id}

    app.dependency_overrides[get_db] = lambda: sesion
    app.dependency_overrides[get_verificador] = lambda: VerificadorToken(secreto=SECRETO_PRUEBA)
    return TestClient(app)


def test_coordinador_activo_puede(cliente_permisos, sesion):
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    r = cliente_permisos.post("/solo-coordinador", headers=encabezados(enzo))
    assert r.status_code == 200
    assert r.json() == {"id": enzo.id}


def test_medico_activo_no_tiene_permiso(cliente_permisos, sesion):
    medico = crear_usuario(sesion, "Carlos Lugones")
    r = cliente_permisos.post("/solo-coordinador", headers=encabezados(medico))
    assert r.status_code == 403
    assert r.json()["codigo"] == "SIN_PERMISO"


def test_coordinador_dado_de_baja_no_pasa_por_su_rol(cliente_permisos, sesion):
    exco = crear_usuario(sesion, "Ex coordinador", rol=RolUsuario.COORDINADOR, estado=EstadoUsuario.BAJA)
    r = cliente_permisos.post("/solo-coordinador", headers=encabezados(exco))
    assert r.status_code == 403
    assert r.json()["codigo"] == "CUENTA_DADA_DE_BAJA"
```

En `backend/tests/test_api_turnos.py`, sumar `encabezados` al import de `fabricas` y agregar, después de los imports:

```python
@pytest.fixture(autouse=True)
def con_sesion(cliente, sesion):
    """GET /api/turnos exige un usuario activo: todas las consultas de este archivo van con sesión."""
    cliente.headers.update(encabezados(crear_usuario(sesion, "Médico que consulta")))
```

- [ ] **Paso 2: correr y ver que fallan**

Run: `.venv/bin/pytest tests/test_api_sesion.py tests/test_permisos.py -q`
Expected: FAIL con `ImportError: cannot import name 'requiere_coordinador' from 'app.auth'` (test_permisos) y 404 en `/api/me` (test_api_sesion).

- [ ] **Paso 3: repositorio de usuarios**

Crear `backend/app/repos/usuarios.py`:

```python
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos import Usuario


def buscar_por_auth_id(sesion: Session, auth_id: uuid.UUID) -> Usuario | None:
    return sesion.scalar(select(Usuario).where(Usuario.auth_id == auth_id))
```

- [ ] **Paso 4: dependencias de usuario en `app/auth.py`**

En `backend/app/auth.py`, sumar los imports:

```python
from sqlalchemy.orm import Session

from app.db import get_db
from app.modelos import EstadoUsuario, RolUsuario, Usuario
from app.repos.usuarios import buscar_por_auth_id
```

Reemplazar la función `usuario_actual` (el enganche de F1) por:

```python
def usuario_registrado(
    identidad: Identidad = Depends(identidad_actual), db: Session = Depends(get_db)
) -> Usuario:
    """Usuario vinculado al token, en cualquier estado. Solo para GET /me."""
    usuario = buscar_por_auth_id(db, identidad.auth_id)
    if usuario is None:
        raise ErrorDominio("USUARIO_NO_REGISTRADO", "La cuenta todavía no completó el registro.", 403)
    return usuario


def usuario_actual(usuario: Usuario = Depends(usuario_registrado)) -> Usuario:
    """Usuario con acceso: estado ACTIVO (D23, D30). Lo exige todo endpoint salvo /health, /me y /registro."""
    if usuario.estado == EstadoUsuario.PENDIENTE:
        raise ErrorDominio("CUENTA_PENDIENTE", "Un coordinador tiene que activar tu cuenta.", 403)
    if usuario.estado == EstadoUsuario.BAJA:
        raise ErrorDominio("CUENTA_DADA_DE_BAJA", "La cuenta está dada de baja.", 403)
    return usuario


def requiere_coordinador(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
    """Permiso validado en el backend aunque la interfaz oculte la acción (regla 7)."""
    if usuario.rol != RolUsuario.COORDINADOR:
        raise ErrorDominio("SIN_PERMISO", "Solo un coordinador puede hacer esta acción.", 403)
    return usuario
```

Cambiar el docstring del módulo a:

```python
"""Autenticación con Supabase Auth (D06) y permisos por estado y rol (D23, D30).

El frontend inicia sesión contra Supabase Auth y manda el token de acceso en Authorization: Bearer.
El backend solo verifica el token: nunca ve ni guarda contraseñas.
Dependencias, de menor a mayor exigencia: identidad_actual (token válido), usuario_registrado
(token vinculado a un Usuario), usuario_actual (Usuario ACTIVO), requiere_coordinador.
"""
```

- [ ] **Paso 5: esquema base compartido**

Crear `backend/app/api/esquemas.py`:

```python
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class Esquema(BaseModel):
    """Base de los esquemas de la API: JSON en camelCase."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
```

En `backend/app/api/turnos.py`:
1. Borrar la clase `_Esquema` y los imports `BaseModel, ConfigDict` y `to_camel` que solo ella usaba.
2. Agregar `from app.api.esquemas import Esquema` y `from app.modelos import Usuario`.
3. Reemplazar `_Esquema` por `Esquema` en `TitularOut` y `TurnoOut`.
4. En `listar_turnos`, cambiar `_usuario: None = Depends(usuario_actual)` por `_usuario: Usuario = Depends(usuario_actual)`.

- [ ] **Paso 6: router de sesión**

Crear `backend/app/api/sesion.py`:

```python
from fastapi import APIRouter, Depends

from app.api.esquemas import Esquema
from app.auth import usuario_registrado
from app.modelos import EstadoUsuario, RolUsuario, Usuario

router = APIRouter()


class UsuarioOut(Esquema):
    id: int
    nombre: str
    email: str
    rol: RolUsuario
    estado: EstadoUsuario


def _a_salida(usuario: Usuario) -> UsuarioOut:
    return UsuarioOut(
        id=usuario.id, nombre=usuario.nombre, email=usuario.email, rol=usuario.rol, estado=usuario.estado
    )


@router.get("/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(usuario_registrado)) -> UsuarioOut:
    """Usuario de la sesión, en cualquier estado: la interfaz muestra "esperando activación" si está PENDIENTE."""
    return _a_salida(usuario)
```

En `backend/app/main.py`, cambiar el import a `from app.api import health, sesion, turnos` y agregar `api.include_router(sesion.router)` después de `api.include_router(health.router)`.

- [ ] **Paso 7: correr y ver que pasan**

Run: `.venv/bin/pytest tests/test_api_sesion.py tests/test_permisos.py tests/test_api_turnos.py -q`
Expected: todas pasan.

Run: `.venv/bin/pytest -q`
Expected: toda la suite pasa.

- [ ] **Paso 8: commit**

```bash
git add backend/app/auth.py backend/app/repos/usuarios.py backend/app/api/esquemas.py backend/app/api/sesion.py backend/app/api/turnos.py backend/app/main.py backend/tests/test_api_sesion.py backend/tests/test_permisos.py backend/tests/test_api_turnos.py
git commit -m "$(cat <<'EOF'
GET /api/me y permisos por estado y rol (D06, D23, D30)

usuario_actual exige una cuenta ACTIVA y requiere_coordinador el rol COORDINADOR; GET /me
responde en cualquier estado. GET /api/turnos pasa a exigir sesión.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarea 4: POST /api/registro con código de coordinación

**Archivos:**
- Crear: `backend/app/dominio/registro.py`
- Modificar: `backend/app/repos/usuarios.py`, `backend/app/api/sesion.py`
- Crear: `backend/tests/test_registro.py`, `backend/tests/test_api_registro.py`

**Interfaces:**
- Consume: `identidad_actual`, `Identidad` (tarea 2); `UsuarioOut`, `_a_salida`, `router` de `app/api/sesion.py` (tarea 3); `get_settings().codigo_coordinacion` (tarea 2).
- Produce: `es_codigo_de_coordinacion(ingresado: str, configurado: str) -> bool` en `app/dominio/registro.py`; `buscar_por_email(sesion, email: str) -> Usuario | None` en `app/repos/usuarios.py`; `POST /api/registro` con cuerpo `{"nombre": str, "codigoCoordinacion": str | null}` que responde `UsuarioOut` (201 si crea, 200 si vincula).

- [ ] **Paso 1: escribir las pruebas que fallan**

Crear `backend/tests/test_registro.py`:

```python
import pytest

from app.dominio.registro import es_codigo_de_coordinacion


@pytest.mark.parametrize(
    "ingresado,configurado,esperado",
    [
        ("SMG", "SMG", True),
        (" smg ", "SMG", True),
        ("SMG", " smg ", True),
        ("SMX", "SMG", False),
        ("SMGX", "SMG", False),
        ("", "SMG", False),
        ("", "", False),
        ("   ", "   ", False),
        ("SMG", "", False),
    ],
)
def test_es_codigo_de_coordinacion(ingresado, configurado, esperado):
    assert es_codigo_de_coordinacion(ingresado, configurado) is esperado
```

Crear `backend/tests/test_api_registro.py`:

```python
import uuid

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.modelos import EstadoUsuario, RolUsuario, Usuario
from fabricas import crear_usuario, token_para

CODIGO = "SMG"


@pytest.fixture(autouse=True)
def codigo_configurado(monkeypatch):
    monkeypatch.setattr(get_settings(), "codigo_coordinacion", CODIGO)


def registrar(cliente, auth_id, email="ana@prueba.test", **cuerpo):
    datos = {"nombre": "Ana Pérez", **cuerpo}
    token = token_para(auth_id, email=email)
    return cliente.post("/api/registro", json=datos, headers={"Authorization": f"Bearer {token}"})


def usuarios_con_cuenta(sesion, auth_id) -> int:
    return sesion.scalar(select(func.count()).select_from(Usuario).where(Usuario.auth_id == auth_id))


def test_sin_codigo_queda_medico_pendiente(cliente, sesion):
    auth_id = uuid.uuid4()

    r = registrar(cliente, auth_id)

    assert r.status_code == 201
    cuerpo = r.json()
    assert {k: cuerpo[k] for k in ("nombre", "email", "rol", "estado")} == {
        "nombre": "Ana Pérez",
        "email": "ana@prueba.test",
        "rol": "MEDICO",
        "estado": "PENDIENTE",
    }
    usuario = sesion.scalar(select(Usuario).where(Usuario.auth_id == auth_id))
    assert usuario.id == cuerpo["id"]


def test_con_codigo_correcto_queda_coordinador_activo(cliente):
    r = registrar(cliente, uuid.uuid4(), codigoCoordinacion=" smg ")

    assert r.status_code == 201
    assert (r.json()["rol"], r.json()["estado"]) == ("COORDINADOR", "ACTIVO")


def test_codigo_incorrecto_es_422_y_no_crea_nada(cliente, sesion):
    auth_id = uuid.uuid4()

    r = registrar(cliente, auth_id, codigoCoordinacion="ABC")

    assert r.status_code == 422
    assert r.json()["codigo"] == "CODIGO_INVALIDO"
    assert usuarios_con_cuenta(sesion, auth_id) == 0


def test_codigo_en_blanco_cuenta_como_sin_codigo(cliente):
    r = registrar(cliente, uuid.uuid4(), codigoCoordinacion="   ")

    assert r.status_code == 201
    assert r.json()["rol"] == "MEDICO"


def test_sin_codigo_configurado_nadie_es_coordinador(cliente, monkeypatch):
    monkeypatch.setattr(get_settings(), "codigo_coordinacion", "")

    r = registrar(cliente, uuid.uuid4(), codigoCoordinacion="SMG")

    assert r.status_code == 422
    assert r.json()["codigo"] == "CODIGO_INVALIDO"


@pytest.mark.parametrize("nombre", ["", "   "])
def test_nombre_vacio_es_error_de_validacion(cliente, nombre):
    r = registrar(cliente, uuid.uuid4(), nombre=nombre)

    assert r.status_code == 422
    assert r.json()["codigo"] == "VALIDACION"


def test_email_cargado_vincula_la_cuenta_y_conserva_el_rol(cliente, sesion):
    enzo = crear_usuario(
        sesion, "Enzo", rol=RolUsuario.COORDINADOR, email="Enzo@GuardiaViva.test", con_cuenta=False
    )
    auth_id = uuid.uuid4()

    r = registrar(cliente, auth_id, email="enzo@guardiaviva.test", nombre="Otro nombre")

    assert r.status_code == 200
    assert r.json() == {
        "id": enzo.id,
        "nombre": "Enzo",
        "email": "Enzo@GuardiaViva.test",
        "rol": "COORDINADOR",
        "estado": "ACTIVO",
    }
    sesion.refresh(enzo)
    assert enzo.auth_id == auth_id


def test_vincular_no_cambia_el_rol_aunque_traiga_el_codigo(cliente, sesion):
    medico = crear_usuario(sesion, "Carlos Lugones", email="carlos@prueba.test", con_cuenta=False)

    r = registrar(cliente, uuid.uuid4(), email="carlos@prueba.test", codigoCoordinacion=CODIGO)

    assert r.status_code == 200
    assert (r.json()["id"], r.json()["rol"]) == (medico.id, "MEDICO")


def test_registrarse_dos_veces_es_409(cliente):
    auth_id = uuid.uuid4()
    assert registrar(cliente, auth_id).status_code == 201

    r = registrar(cliente, auth_id)

    assert r.status_code == 409
    assert r.json()["codigo"] == "YA_REGISTRADO"


def test_email_de_otra_cuenta_es_409(cliente, sesion):
    crear_usuario(sesion, "Ana Pérez", email="ana@prueba.test")

    r = registrar(cliente, uuid.uuid4(), email="ana@prueba.test")

    assert r.status_code == 409
    assert r.json()["codigo"] == "EMAIL_YA_REGISTRADO"


def test_cuenta_vinculada_con_otro_email_choca_con_la_restriccion_de_la_base(cliente, sesion):
    """Regla 8: el duplicado de cuenta lo detecta la restricción única de auth_id, no una consulta previa."""
    ana = crear_usuario(sesion, "Ana Pérez", email="ana@prueba.test")
    # El endpoint hace rollback al chocar: sin este commit (que en la sesión de pruebas libera el
    # savepoint, sin confirmar la transacción externa), el rollback se llevaría también a Ana.
    sesion.commit()

    r = registrar(cliente, ana.auth_id, email="ana.nueva@prueba.test")

    assert r.status_code == 409
    assert r.json()["codigo"] == "YA_REGISTRADO"
    assert usuarios_con_cuenta(sesion, ana.auth_id) == 1


def test_token_sin_email_es_401(cliente):
    r = registrar(cliente, uuid.uuid4(), email=None)

    assert r.status_code == 401
    assert r.json()["codigo"] == "TOKEN_SIN_EMAIL"


def test_registro_sin_token_es_401(cliente):
    r = cliente.post("/api/registro", json={"nombre": "Ana Pérez"})

    assert r.status_code == 401
    assert r.json()["codigo"] == "SIN_SESION"


def test_despues_del_registro_me_responde_pendiente(cliente):
    auth_id = uuid.uuid4()
    registrar(cliente, auth_id)

    r = cliente.get("/api/me", headers={"Authorization": f"Bearer {token_para(auth_id, email='ana@prueba.test')}"})

    assert r.status_code == 200
    assert r.json()["estado"] == EstadoUsuario.PENDIENTE.value
```

- [ ] **Paso 2: correr y ver que fallan**

Run: `.venv/bin/pytest tests/test_registro.py tests/test_api_registro.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.dominio.registro'` y 404/405 en `/api/registro`.

- [ ] **Paso 3: implementar la regla del código**

Crear `backend/app/dominio/registro.py`:

```python
"""Registro con código de coordinación (D30)."""

import hmac


def es_codigo_de_coordinacion(ingresado: str, configurado: str) -> bool:
    """Compara sin distinguir mayúsculas ni espacios en los extremos, en tiempo constante.

    Sin código configurado en el servidor, ningún código es válido: nadie se registra como coordinador.
    """
    esperado = configurado.strip().upper()
    if not esperado:
        return False
    return hmac.compare_digest(ingresado.strip().upper().encode(), esperado.encode())
```

- [ ] **Paso 4: búsqueda por email**

En `backend/app/repos/usuarios.py`, sumar `func` al import de `sqlalchemy` y agregar:

```python
def buscar_por_email(sesion: Session, email: str) -> Usuario | None:
    """Sin distinguir mayúsculas, como el índice único ux_usuario_email_lower."""
    return sesion.scalar(select(Usuario).where(func.lower(Usuario.email) == email.lower()))
```

- [ ] **Paso 5: implementar el endpoint**

En `backend/app/api/sesion.py`, reemplazar los imports por:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import Field, StringConstraints
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.esquemas import Esquema
from app.auth import Identidad, identidad_actual, usuario_registrado
from app.config import get_settings
from app.db import get_db
from app.dominio.registro import es_codigo_de_coordinacion
from app.errores import ErrorDominio
from app.modelos import EstadoUsuario, RolUsuario, Usuario
from app.repos.usuarios import buscar_por_email
```

y agregar al final del archivo:

```python
# Restricción violada -> (código, mensaje) del 409. Regla 8: la carrera entre dos registros la resuelve la base.
_CONFLICTOS_DE_REGISTRO = {
    "usuario_auth_id_key": ("YA_REGISTRADO", "Esta cuenta ya está registrada."),
    "ux_usuario_email_lower": ("EMAIL_YA_REGISTRADO", "Ese email ya está registrado con otra cuenta."),
}


class RegistroIn(Esquema):
    nombre: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    codigo_coordinacion: str | None = Field(default=None, max_length=64)


@router.post("/registro", response_model=UsuarioOut, status_code=201)
def registrar(
    datos: RegistroIn,
    respuesta: Response,
    identidad: Identidad = Depends(identidad_actual),
    db: Session = Depends(get_db),
) -> UsuarioOut:
    """Completa el registro de una cuenta ya creada en Supabase Auth (D30).

    Con el código de coordinación correcto queda COORDINADOR ACTIVO; sin código, MEDICO PENDIENTE hasta
    que un coordinador lo active. Si el email ya estaba cargado sin cuenta (datos de ejemplo, D28),
    vincula la cuenta, conserva nombre, rol y estado, y responde 200.
    """
    if identidad.email is None:
        raise ErrorDominio("TOKEN_SIN_EMAIL", "El token de sesión no trae el email de la cuenta.", 401)
    codigo = (datos.codigo_coordinacion or "").strip()
    if codigo and not es_codigo_de_coordinacion(codigo, get_settings().codigo_coordinacion):
        raise ErrorDominio("CODIGO_INVALIDO", "El código de coordinación no es correcto.", 422)

    existente = buscar_por_email(db, identidad.email)
    if existente is not None and existente.auth_id == identidad.auth_id:
        raise ErrorDominio("YA_REGISTRADO", "Esta cuenta ya está registrada.", 409)
    if existente is not None and existente.auth_id is not None:
        raise ErrorDominio("EMAIL_YA_REGISTRADO", "Ese email ya está registrado con otra cuenta.", 409)

    if existente is not None:
        existente.auth_id = identidad.auth_id
        usuario = existente
        respuesta.status_code = 200
    else:
        coordinador = bool(codigo)
        usuario = Usuario(
            nombre=datos.nombre,
            email=identidad.email,
            rol=RolUsuario.COORDINADOR if coordinador else RolUsuario.MEDICO,
            estado=EstadoUsuario.ACTIVO if coordinador else EstadoUsuario.PENDIENTE,
            auth_id=identidad.auth_id,
        )
        db.add(usuario)

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        restriccion = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if restriccion not in _CONFLICTOS_DE_REGISTRO:
            raise
        codigo_error, mensaje = _CONFLICTOS_DE_REGISTRO[restriccion]
        raise ErrorDominio(codigo_error, mensaje, 409) from exc
    db.commit()
    return _a_salida(usuario)
```

- [ ] **Paso 6: correr y ver que pasan**

Run: `.venv/bin/pytest tests/test_registro.py tests/test_api_registro.py -q`
Expected: todas pasan.

Run: `.venv/bin/pytest -q`
Expected: toda la suite pasa.

- [ ] **Paso 7: commit**

```bash
git add backend/app/dominio/registro.py backend/app/repos/usuarios.py backend/app/api/sesion.py backend/tests/test_registro.py backend/tests/test_api_registro.py
git commit -m "$(cat <<'EOF'
POST /api/registro con código de coordinación (D30, D28)

Con el código correcto la cuenta queda coordinador activo; sin código, médico pendiente.
Un email ya cargado sin cuenta se vincula y conserva su rol. Los duplicados de cuenta o de
email responden 409 desde las restricciones de la base.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarea 5: documentación

**Archivos:**
- Modificar: `backend/CLAUDE.md`, `docs/plan-de-implementacion.md`, `docs/prompts-principales.md`

**Interfaces:**
- Consume: todo lo anterior. No produce código.

- [ ] **Paso 1: `backend/CLAUDE.md`**

En "Estructura", reemplazar el punto 7 por:

```markdown
7. `app/auth.py`: verificación del token de Supabase Auth (D06) y dependencias de permisos: `identidad_actual` (token válido), `usuario_registrado` (solo GET /me), `usuario_actual` (cuenta ACTIVA; la exige todo endpoint salvo /health, /me y /registro) y `requiere_coordinador`.
```

En "Convenciones", agregar:

```markdown
7. Pruebas con sesión: `crear_usuario` crea usuarios con cuenta de Supabase (`con_cuenta=False` para simular los del seed) y `encabezados(usuario)` arma el `Authorization: Bearer`. La fixture `cliente` verifica tokens con `SECRETO_PRUEBA`; `token_para(...)` arma tokens a medida (vencidos, sin email, otro algoritmo).
8. Los instantes de dominio (`creada_en` de vacante, postulación y notificación; `ocurrido_en` del evento; `cerrada_en`, `consolidado_en`, etc.) no tienen valor por defecto en la base: se completan con `reloj.ahora()`.
9. `evento_turno` solo admite INSERT: un trigger rechaza UPDATE y DELETE (D22). TRUNCATE sigue funcionando para el seed y las pruebas.
10. El vencimiento del token se controla con la hora real dentro de PyJWT, no con el reloj inyectable, para que adelantar el reloj de demo no cierre las sesiones.
```

En "Comandos", después de la línea de `cp .env.example .env`, agregar:

```bash
# completar también SUPABASE_URL (o SUPABASE_JWT_SECRET) y CODIGO_COORDINACION; en Supabase, Authentication > Sign In / Providers > Email: desactivar "Confirm email" (D06)
```

- [ ] **Paso 2: `docs/plan-de-implementacion.md`**

En la tabla "Orden de funcionalidades", reemplazar la fila de F2 por:

```markdown
| F2 | Cimientos | Supabase Auth (D06, D07), POST /registro con código de coordinación (D30), GET /me, permisos por estado y rol; tablas Turno, Vacante, Postulacion, EventoTurno y Notificacion en una sola migración | 7/10 |
| F2b | Vacantes y postulaciones | Reglas de vacantes (incluida la urgente) y postulaciones, semáforo calculado, elegibilidad, bitácora, logs de dominio legibles en la terminal (una línea por acción). Otro integrante, sobre las tablas de F2 | 8/10 |
```

y en la fila de F5 quitar "Supabase Auth con email y contraseña, registro con código de coordinación (D30), " y "RLS, " (ya hechos en F2), dejando: `Estados de usuario, API de staff, baja con horarios sin titular (D24)`.

- [ ] **Paso 3: `docs/prompts-principales.md`**

Antes de "## Próximas entradas", agregar:

```markdown
## 4. F2: cimientos

Fecha: 7/10/2026.
Herramienta: Claude Code con Superpowers (writing-plans; sin brainstorming ni spec propio: el plan se apoya en las decisiones de arquitectura).
Prompt:

> Leé backend/CLAUDE.md y el documento de decisiones de arquitectura en docs. Vamos a hacer la fase F2 "cimientos": autenticación con Supabase Auth (D06, D07), POST /api/registro con código de coordinación (D30), GET /api/me, y los modelos Turno, Vacante, Postulacion, EventoTurno y Notificacion según D08 a D25, todos en una única migración de Alembic. No implementes reglas de negocio ni endpoints de vacantes o postulaciones: eso lo hace otro integrante. Usá Superpowers: escribí el plan en docs/superpowers/plans, trabajá en la branch feature/f2-cimientos y un commit por tarea. Por ahora solo escribí el plan, mostrámelo para aprobarlo y commitealo en la branch. No ejecutes ninguna tarea hasta que te lo pida.

Resultado: plan en `docs/superpowers/plans/2026-10-07-f2-cimientos.md`, con 13 decisiones que D06 a D30 dejaban abiertas (entre ellas, vencimiento del token con la hora real y vinculación por email de los usuarios del seed) para aprobar antes de ejecutar.
```

- [ ] **Paso 4: verificación final**

Run (desde la raíz): `docker compose up -d --wait`
Run (desde `backend/`): `.venv/bin/pytest -q`
Expected: toda la suite pasa. No se tocó el frontend: la prueba e2e de `/api/health` no cambia y no hace falta Playwright.

Run: `grep -rn "datetime.now\|date.today\|time.time" backend/app`
Expected: solo aparece `app/reloj.py`.

- [ ] **Paso 5: commit**

```bash
git add backend/CLAUDE.md docs/plan-de-implementacion.md docs/prompts-principales.md
git commit -m "$(cat <<'EOF'
Documentación de F2: autenticación, convenciones de prueba y nuevo orden de fases

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Tarea 6: el seed conserva los vínculos con las cuentas de Supabase

Hoy `scripts/seed.py` hace TRUNCATE de `usuario`, y con eso pierde el `auth_id` de quienes ya se registraron. Después de cada reinicio de la demo, Enzo y los médicos tendrían que volver a pasar por `POST /api/registro`. Esta tarea hace que cada usuario de ejemplo recupere la cuenta que tenía el usuario con el mismo email (decisión 14).

**Archivos:**
- Modificar: `backend/scripts/seed.py`, `backend/tests/test_seed.py`, `backend/CLAUDE.md`

**Interfaces:**
- Consume: `Usuario` (F1), `crear_usuario(..., con_cuenta=...)` de `tests/fabricas.py` (tarea 2).
- Produce: `cargar_datos_ejemplo(sesion) -> int`, que ahora devuelve cuántos vínculos con Supabase Auth conservó (antes devolvía `None`). `main` lo informa.

- [ ] **Paso 1: escribir las pruebas que fallan**

En `backend/tests/test_seed.py`, sumar `import uuid` y `from fabricas import crear_usuario` a los imports, y agregar al final:

```python
def coordinador(sesion) -> Usuario:
    return sesion.scalar(select(Usuario).where(Usuario.rol == RolUsuario.COORDINADOR))


def test_seed_conserva_los_vinculos_con_supabase(sesion):
    cargar_datos_ejemplo(sesion)
    enzo = coordinador(sesion)
    cuenta = uuid.uuid4()
    enzo.auth_id = cuenta
    enzo.email = enzo.email.upper()  # el vínculo se busca sin distinguir mayúsculas
    sesion.flush()

    conservados = cargar_datos_ejemplo(sesion)

    assert conservados == 1
    enzo = coordinador(sesion)
    assert enzo.auth_id == cuenta
    assert enzo.email == "enzo@guardiaviva.test"
    con_cuenta = sesion.scalar(select(func.count()).select_from(Usuario).where(Usuario.auth_id.is_not(None)))
    assert con_cuenta == 1


def test_seed_sin_vinculos_previos_no_vincula_nada(sesion):
    assert cargar_datos_ejemplo(sesion) == 0
    assert sesion.scalar(select(func.count()).select_from(Usuario).where(Usuario.auth_id.is_not(None))) == 0


def test_seed_borra_usuarios_que_no_son_de_ejemplo_aunque_tengan_cuenta(sesion):
    cargar_datos_ejemplo(sesion)
    crear_usuario(sesion, "Registrada desde la app", email="nueva@prueba.test")

    assert cargar_datos_ejemplo(sesion) == 0
    assert sesion.scalar(select(func.count()).select_from(Usuario)) == 11
```

Estas pruebas guardan referencias a usuarios de la carga anterior mientras se vuelve a cargar. Con los mismos ids (RESTART IDENTITY), el mapa de identidad de la sesión chocaría con los usuarios nuevos; por eso la implementación vacía ese mapa después del TRUNCATE.

- [ ] **Paso 2: correr y ver que fallan**

Run: `.venv/bin/pytest tests/test_seed.py -q`
Expected: FAIL. `test_seed_conserva_los_vinculos_con_supabase` falla porque `cargar_datos_ejemplo` devuelve `None` (o por el choque del mapa de identidad), y `test_seed_sin_vinculos_previos_no_vincula_nada` porque `None != 0`.

- [ ] **Paso 3: implementar**

En `backend/scripts/seed.py`, sumar `import uuid` y cambiar el import de SQLAlchemy a `from sqlalchemy import func, select, text`. Agregar antes de `cargar_datos_ejemplo`:

```python
def _vinculos_con_supabase(sesion: Session) -> dict[str, uuid.UUID]:
    """Cuentas de Supabase Auth ya vinculadas, por email en minúsculas (D06, D28)."""
    filas = sesion.execute(
        select(func.lower(Usuario.email), Usuario.auth_id).where(Usuario.auth_id.is_not(None))
    ).all()
    return {email: auth_id for email, auth_id in filas}
```

Reemplazar el comienzo de `cargar_datos_ejemplo`, desde la firma hasta el `sesion.flush()` que sigue al coordinador inclusive, por:

```python
def cargar_datos_ejemplo(sesion: Session) -> int:
    """Vacía las tablas y carga usuarios y horarios. No hace commit.

    Cada usuario de ejemplo recupera la cuenta de Supabase Auth que tenía el usuario con su mismo email,
    así nadie tiene que volver a registrarse después de reiniciar la demo. Devuelve cuántas conservó.
    """
    vinculos = _vinculos_con_supabase(sesion)
    sesion.execute(text("TRUNCATE usuario, horario_pactado, version_horario RESTART IDENTITY CASCADE"))
    # RESTART IDENTITY reutiliza los ids: los objetos de la carga anterior no deben chocar con los nuevos.
    sesion.expunge_all()

    def nuevo_usuario(nombre: str, usuario: str, rol: RolUsuario) -> Usuario:
        email = _email(usuario)
        fila = Usuario(
            nombre=nombre,
            email=email,
            rol=rol,
            estado=EstadoUsuario.ACTIVO,
            auth_id=vinculos.get(email.lower()),
        )
        sesion.add(fila)
        sesion.flush()
        return fila

    ids: dict[str, int] = {}
    for nombre, usuario in MEDICOS:
        ids[usuario] = nuevo_usuario(nombre, usuario, RolUsuario.MEDICO).id
    nombre, usuario = COORDINADOR
    nuevo_usuario(nombre, usuario, RolUsuario.COORDINADOR)
    conservados = sum(1 for _, usuario in [*MEDICOS, COORDINADOR] if _email(usuario).lower() in vinculos)
```

Al final de la función, después del bucle de `HORARIOS`, agregar:

```python
    return conservados
```

En `main`, reemplazar el bloque de la carga y su mensaje por:

```python
    with SessionLocal() as sesion, sesion.begin():
        conservados = cargar_datos_ejemplo(sesion)
    print(f"Datos de ejemplo cargados: {len(MEDICOS)} médicos, 1 coordinador, {len(HORARIOS)} horarios.")
    print(f"Cuentas de Supabase conservadas: {conservados}.")
```

Actualizar el docstring del módulo: después de "Vacía las tablas y vuelve a cargar todo: correrlo dos veces deja el mismo estado y los mismos ids." agregar "Conserva los vínculos con Supabase Auth de los usuarios de ejemplo (por email); los demás usuarios se borran."

- [ ] **Paso 4: correr y ver que pasan**

Run: `.venv/bin/pytest tests/test_seed.py -q`
Expected: todas pasan, incluidas las anteriores (`test_seed_dos_veces_deja_el_mismo_estado`, `test_seed_vacia_las_tablas_operativas`).

Run: `.venv/bin/pytest -q`
Expected: toda la suite pasa.

- [ ] **Paso 5: probar el script contra la base local de desarrollo (nunca Supabase)**

Run: `DATABASE_URL=postgresql://guardia:guardia@localhost:5433/guardia .venv/bin/alembic upgrade head && DATABASE_URL=postgresql://guardia:guardia@localhost:5433/guardia .venv/bin/python -m scripts.seed --confirmar`
Expected: imprime `Base de destino: localhost:5433/guardia`, la línea de datos cargados y `Cuentas de Supabase conservadas: 0.`

- [ ] **Paso 6: documentación**

En `backend/CLAUDE.md`, reemplazar el punto 8 de "Estructura" por:

```markdown
8. `scripts/seed.py`: datos de ejemplo. Al recargar conserva, por email, las cuentas de Supabase Auth de los usuarios de ejemplo; los usuarios que no son de ejemplo se borran.
```

En `docs/prompts-principales.md`, al final de la entrada "4. F2: cimientos", agregar:

```markdown
Corrección al aprobar el plan: "Agregá una tarea 6: que el script de datos de ejemplo conserve los vínculos con las cuentas de Supabase al volver a correrse." Se ejecuta en la misma sesión, con revisión de código de toda la branch antes del pull request.
```

- [ ] **Paso 7: commit**

```bash
git add backend/scripts/seed.py backend/tests/test_seed.py backend/CLAUDE.md docs/prompts-principales.md
git commit -m "$(cat <<'EOF'
El seed conserva las cuentas de Supabase de los usuarios de ejemplo (D06, D28)

Al reiniciar la demo, cada usuario de ejemplo recupera por email el auth_id que tenía,
así nadie tiene que volver a registrarse.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Después de la tarea 6: revisión de toda la branch

- [ ] Correr `.venv/bin/pytest -q` (desde `backend/`) y confirmar que toda la suite pasa.
- [ ] Revisión de código de `main..feature/f2-cimientos` con superpowers:requesting-code-review, contra este plan y `docs/decisiones-arquitectura.md`. Corregir lo que corresponda, con un commit por corrección, y anotar en `docs/bitacora-de-desvios.md` cada desvío o error que encuentre la revisión.
- [ ] Recién entonces, abrir el pull request a `main` (lo revisa otro integrante en GitHub antes del merge).
