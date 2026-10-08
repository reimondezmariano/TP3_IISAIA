import Cargando from "./componentes/Cargando.jsx";
import Acceso from "./pantallas/Acceso.jsx";
import CompletarRegistro from "./pantallas/CompletarRegistro.jsx";
import CuentaSinAcceso from "./pantallas/CuentaSinAcceso.jsx";
import Principal from "./pantallas/Principal.jsx";
import { useSesion } from "./sesion/useSesion.js";

export default function App() {
  const { estado, aviso, recargar, cerrarSesion } = useSesion();
  switch (estado) {
    case "cargando":
      return <Cargando />;
    case "anonimo":
      return <Acceso />;
    case "sin-registro":
      return <CompletarRegistro />;
    case "pendiente":
    case "baja":
      return <CuentaSinAcceso />;
    case "activo":
      return <Principal />;
    default:
      return (
        <main className="acceso">
          <h1>Guardia Viva</h1>
          <p role="alert" className="error">{aviso ?? "No se pudo cargar tu cuenta."}</p>
          <div className="acciones">
            <button type="button" onClick={recargar}>Reintentar</button>
            <button type="button" className="secundario" onClick={cerrarSesion}>Cerrar sesión</button>
          </div>
        </main>
      );
  }
}
