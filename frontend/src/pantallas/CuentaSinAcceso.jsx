import { useSesion } from "../sesion/useSesion.js";

export default function CuentaSinAcceso() {
  const { estado, usuario, recargar, cerrarSesion } = useSesion();
  const pendiente = estado === "pendiente";
  return (
    <main className="acceso">
      <h1>{pendiente ? "Esperando activación" : "Cuenta dada de baja"}</h1>
      <p>
        {pendiente
          ? "Un coordinador tiene que activar tu cuenta antes de que puedas ver las guardias."
          : "Tu cuenta ya no tiene acceso. Si es un error, hablá con un coordinador."}
      </p>
      {usuario && <p className="chico">Ingresaste como {usuario.nombre} ({usuario.email}).</p>}
      <div className="acciones">
        {pendiente && <button type="button" onClick={recargar}>Actualizar</button>}
        <button type="button" className="secundario" onClick={cerrarSesion}>Cerrar sesión</button>
      </div>
    </main>
  );
}
