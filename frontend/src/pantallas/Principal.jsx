import { useSesion } from "../sesion/useSesion.js";
import AvisoUrgente from "../notificaciones/AvisoUrgente.jsx";
import Campanita from "../notificaciones/Campanita.jsx";
import { useNotificaciones } from "../notificaciones/useNotificaciones.js";
import Calendario from "./Calendario.jsx";

// Pantalla de una cuenta activa: barra con la campanita y la pantalla elegida.
export default function Principal() {
  const { api } = useSesion();
  const notificaciones = useNotificaciones(api);
  return (
    <>
      <div className="barra-superior">
        <Campanita notificaciones={notificaciones} />
      </div>
      <Calendario />
      <AvisoUrgente notificaciones={notificaciones} />
    </>
  );
}
