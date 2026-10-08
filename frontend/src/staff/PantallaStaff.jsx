import { useEffect, useState } from "react";
import Cargando from "../componentes/Cargando.jsx";
import { fechaLocal, sumarDias } from "../lib/fechas.js";
import DesignarTitular from "./DesignarTitular.jsx";
import FilaUsuario from "./FilaUsuario.jsx";
import FormularioHorario from "./FormularioHorario.jsx";
import { describirHorario, versionActual } from "./formato.js";
import TurnosAfectados from "./TurnosAfectados.jsx";
import { useStaff } from "./useStaff.js";

// "Hoy" del servidor (D27); si /health falla, el del navegador.
function useHoy(api) {
  const [hoy, setHoy] = useState(null);
  useEffect(() => {
    let vigente = true;
    api
      .get("/api/health")
      .then((salud) => (Number.isNaN(Date.parse(salud?.ahora)) ? new Date().toISOString() : salud.ahora))
      .catch(() => new Date().toISOString())
      .then((instante) => vigente && setHoy(fechaLocal(instante)));
    return () => {
      vigente = false;
    };
  }, [api]);
  return hoy;
}

export default function PantallaStaff({ api, usuario }) {
  const hoy = useHoy(api);
  const staff = useStaff(api);
  if (hoy === null || staff.estado === "cargando") return <Cargando texto="Cargando el staff…" />;
  if (staff.estado === "error") {
    return (
      <main className="calendario">
        <p role="alert" className="error">{staff.error.message}</p>
        <button type="button" onClick={staff.recargar}>Reintentar</button>
      </main>
    );
  }
  return <Contenido staff={staff} usuario={usuario} hoy={hoy} />;
}

function Contenido({ staff, usuario, hoy }) {
  const [resultado, setResultado] = useState(null);
  const [editando, setEditando] = useState(null); // id del horario en modificación, o "nuevo"
  const manana = sumarDias(hoy, 1);
  const medicosActivos = staff.usuarios.filter((u) => u.rol === "MEDICO" && u.estado === "ACTIVO");

  // Muestra lo que pasó con los turnos ya guardados y deja la lista actualizada.
  const informar = (titulo) => (respuesta) => {
    setResultado({
      titulo,
      turnosAfectados: respuesta.turnosAfectados,
      coberturasReabiertas: respuesta.coberturasReabiertas,
      horariosSinTitular: respuesta.horariosSinTitular,
    });
    setEditando(null);
    return respuesta;
  };
  const acciones = {
    activar: async (id) => informar("Médico activado.")(await staff.activar(id)),
    cambiarRol: async (id, rol) => informar(`Rol cambiado a ${rol === "COORDINADOR" ? "coordinador" : "médico"}.`)(await staff.cambiarRol(id, rol)),
    darDeBaja: async (id, fecha) => informar("Baja registrada.")(await staff.darDeBaja(id, fecha)),
  };

  const conTitular = staff.horarios.filter((h) => h.estado !== "CERRADO");
  const sinTitular = conTitular.filter((h) => h.estado === "SIN_TITULAR");

  return (
    <main className="calendario staff">
      <header className="cabecera">
        <h2>Staff y horarios</h2>
        <button type="button" className="secundario" onClick={staff.recargar}>Actualizar</button>
      </header>
      {resultado && <TurnosAfectados resultado={resultado} onCerrar={() => setResultado(null)} />}

      <section aria-labelledby="titulo-personas">
        <h3 id="titulo-personas">Personas</h3>
        <ul className="lista-staff">
          {staff.usuarios.map((u) => (
            <FilaUsuario key={u.id} usuario={u} esYo={u.id === usuario.id} hoy={hoy} acciones={acciones} />
          ))}
        </ul>
      </section>

      {sinTitular.length > 0 && (
        <section aria-labelledby="titulo-baja">
          <h3 id="titulo-baja">Horarios sin titular (BAJA)</h3>
          <ul className="lista-staff">
            {sinTitular.map((h) => {
              const v = versionActual(h, hoy);
              return (
                <li key={h.id} className="fila-usuario" data-horario-id={h.id}>
                  <p><span className="insignia baja">BAJA</span> {describirHorario(v)}</p>
                  <DesignarTitular
                    medicos={medicosActivos}
                    desdePorDefecto={manana}
                    onDesignar={async (cuerpo) => informar("Nuevo titular designado.")(await staff.nuevaVersion(h.id, cuerpo))}
                  />
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <section aria-labelledby="titulo-horarios">
        <h3 id="titulo-horarios">Horarios</h3>
        <ul className="lista-staff">
          {conTitular.map((h) => {
            const v = versionActual(h, hoy);
            return (
              <li key={h.id} className="fila-usuario" data-horario-id={h.id}>
                <p>
                  <strong>{v.medico ? v.medico.nombre : "Sin titular"}</strong> · {describirHorario(v)}
                  {v.vigenteDesde > hoy && <span className="chico"> (rige desde {v.vigenteDesde})</span>}
                </p>
                {editando === h.id ? (
                  <FormularioHorario
                    modo="modificar"
                    medicos={medicosActivos}
                    inicial={v}
                    desdePorDefecto={manana}
                    onEnviar={async (cuerpo) => informar("Horario modificado.")(await staff.nuevaVersion(h.id, cuerpo))}
                    onCancelar={() => setEditando(null)}
                  />
                ) : (
                  <button type="button" className="secundario" onClick={() => setEditando(h.id)}>Modificar</button>
                )}
              </li>
            );
          })}
        </ul>
        {editando === "nuevo" ? (
          <FormularioHorario
            modo="crear"
            medicos={medicosActivos}
            desdePorDefecto={manana}
            onEnviar={async (cuerpo) => informar("Horario cargado.")(await staff.crearHorario(cuerpo))}
            onCancelar={() => setEditando(null)}
          />
        ) : (
          <button type="button" onClick={() => setEditando("nuevo")}>Cargar horario nuevo</button>
        )}
      </section>
    </main>
  );
}
