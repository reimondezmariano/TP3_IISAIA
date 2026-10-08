import { useState } from "react";
import { useEnvio } from "../pantallas/useEnvio.js";
import { describirHorario } from "./formato.js";

const ESTADOS = { PENDIENTE: "Pendiente", ACTIVO: "Activo", BAJA: "Baja" };
const ROLES = { MEDICO: "Médico", COORDINADOR: "Coordinador" };

export default function FilaUsuario({ usuario, esYo, hoy, acciones }) {
  const [modo, setModo] = useState(null); // null | "rol" | "baja"
  const [fechaBaja, setFechaBaja] = useState(hoy);
  const { enviando, error, enviar: ejecutar } = useEnvio(async () => {
    if (modo === "rol") {
      await acciones.cambiarRol(usuario.id, usuario.rol === "MEDICO" ? "COORDINADOR" : "MEDICO");
    } else if (modo === "baja") {
      if (!fechaBaja) throw new Error("Elegí el último día activo.");
      await acciones.darDeBaja(usuario.id, fechaBaja);
    }
    setModo(null);
  });
  const activar = useEnvio(() => acciones.activar(usuario.id));
  const rolNuevo = usuario.rol === "MEDICO" ? "coordinador" : "médico";
  const activoOPendiente = usuario.estado !== "BAJA";

  return (
    <li className="fila-usuario" data-usuario-id={usuario.id}>
      <div>
        <strong>{usuario.nombre}</strong> {esYo && <span className="chico">(vos)</span>}
        <p className="chico">{usuario.email}</p>
        <p>
          <span className="insignia">{ROLES[usuario.rol]}</span>{" "}
          <span className={`insignia ${usuario.estado === "BAJA" ? "baja" : usuario.estado === "PENDIENTE" ? "vacante" : "mia"}`}>
            {ESTADOS[usuario.estado]}{usuario.fechaBaja ? ` hasta el ${usuario.fechaBaja}` : ""}
          </span>
        </p>
        {usuario.horarios.length > 0 && (
          <ul className="horarios-de">
            {usuario.horarios.map((h) => (
              <li key={`${h.horarioId}:${h.vigenteDesde}`}>{describirHorario(h)}</li>
            ))}
          </ul>
        )}
      </div>
      {modo === null && (
        <div className="acciones">
          {usuario.estado === "PENDIENTE" && (
            <button type="button" disabled={activar.enviando} onClick={activar.enviar}>{activar.enviando ? "Activando…" : "Activar"}</button>
          )}
          {activoOPendiente && !esYo && usuario.estado === "ACTIVO" && (
            <button type="button" className="secundario" onClick={() => setModo("rol")}>Pasar a {rolNuevo}</button>
          )}
          {usuario.estado === "ACTIVO" && usuario.rol === "MEDICO" && (
            <button type="button" className="secundario" onClick={() => setModo("baja")}>Dar de baja</button>
          )}
        </div>
      )}
      {modo === "rol" && (
        <form onSubmit={ejecutar}>
          <p>
            ¿Pasar a {usuario.nombre} a {rolNuevo}?
            {usuario.rol === "MEDICO" && " Sus horarios quedan sin titular y sus coberturas futuras se reabren."}
          </p>
          <div className="acciones">
            <button type="submit" disabled={enviando}>{enviando ? "Guardando…" : "Confirmar"}</button>
            <button type="button" className="secundario" onClick={() => setModo(null)}>Cancelar</button>
          </div>
        </form>
      )}
      {modo === "baja" && (
        <form onSubmit={ejecutar} noValidate>
          <label>
            Último día activo
            <input type="date" value={fechaBaja} onChange={(e) => setFechaBaja(e.target.value)} />
          </label>
          <p className="chico">Desde el día siguiente sus horarios quedan sin titular y sus coberturas futuras se reabren.</p>
          <div className="acciones">
            <button type="submit" disabled={enviando}>{enviando ? "Guardando…" : "Confirmar baja"}</button>
            <button type="button" className="secundario" onClick={() => setModo(null)}>Cancelar</button>
          </div>
        </form>
      )}
      {(error || activar.error) && <p role="alert" className="error">{error ?? activar.error}</p>}
    </li>
  );
}
