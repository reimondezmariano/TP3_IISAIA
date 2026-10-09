import { useState } from "react";
import { useSesion } from "../sesion/useSesion.js";
import AvisoUrgente from "../notificaciones/AvisoUrgente.jsx";
import Campanita from "../notificaciones/Campanita.jsx";
import { useNotificaciones } from "../notificaciones/useNotificaciones.js";
import PantallaStaff from "../staff/PantallaStaff.jsx";
import Calendario from "./Calendario.jsx";

// Pantalla de una cuenta activa: barra con la campanita y la pantalla elegida. Staff es solo para
// coordinadores (el servidor lo vuelve a validar).
export default function Principal() {
  const { api, usuario } = useSesion();
  const notificaciones = useNotificaciones(api);
  const [pantalla, setPantalla] = useState("calendario");
  const esCoordinador = usuario?.rol === "COORDINADOR";
  const verStaff = esCoordinador && pantalla === "staff";
  return (
    <>
      <header className="barra-superior">
        <div className="marca">
          <span className="marca-logo" aria-hidden="true">GV</span>
          <h1>Guardia Viva</h1>
        </div>
        {esCoordinador && (
          <nav className="pestanas" aria-label="Pantallas">
            <button type="button" aria-pressed={!verStaff} onClick={() => setPantalla("calendario")}>Calendario</button>
            <button type="button" aria-pressed={verStaff} onClick={() => setPantalla("staff")}>Staff</button>
          </nav>
        )}
        <Campanita notificaciones={notificaciones} onIr={esCoordinador ? setPantalla : undefined} />
      </header>
      {verStaff ? <PantallaStaff api={api} usuario={usuario} /> : <Calendario />}
      <AvisoUrgente notificaciones={notificaciones} />
    </>
  );
}
