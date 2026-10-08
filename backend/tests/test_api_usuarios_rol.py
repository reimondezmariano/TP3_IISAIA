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


def test_un_pendiente_no_pasa_a_coordinador_sin_activarse(cliente, sesion, como_coordinador):
    pendiente = crear_usuario(sesion, "Sin activar", estado=EstadoUsuario.PENDIENTE)
    r = cliente.patch(f"/api/usuarios/{pendiente.id}", json={"rol": "COORDINADOR"})
    assert (r.status_code, r.json()["codigo"]) == (409, "USUARIO_PENDIENTE")
    assert [u["rol"] for u in cliente.get("/api/usuarios").json() if u["id"] == pendiente.id] == ["MEDICO"]
