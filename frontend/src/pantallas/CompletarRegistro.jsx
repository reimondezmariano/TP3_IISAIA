import { useState } from "react";
import { useSesion } from "../sesion/useSesion.js";
import { useEnvio } from "./useEnvio.js";

export default function CompletarRegistro() {
  const { completarRegistro, cerrarSesion, aviso, nombreSugerido } = useSesion();
  const [nombre, setNombre] = useState(nombreSugerido ?? "");
  const [codigo, setCodigo] = useState("");
  const { enviando, error, enviar } = useEnvio(() => completarRegistro({ nombre, codigo }));
  const mensaje = error ?? aviso;

  return (
    <main className="acceso">
      <h1>Completá tu registro</h1>
      <p>Tu cuenta de ingreso existe, pero falta terminar el registro en Guardia Viva.</p>
      <form onSubmit={enviar}>
        <label>
          Nombre
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} autoComplete="name" required maxLength={120} />
        </label>
        <label>
          Código de coordinación (opcional)
          <input value={codigo} onChange={(e) => setCodigo(e.target.value)} autoComplete="off" maxLength={64} />
        </label>
        {mensaje && <p role="alert" className="error">{mensaje}</p>}
        <button type="submit" disabled={enviando}>{enviando ? "Enviando…" : "Completar registro"}</button>
      </form>
      <button type="button" className="secundario" onClick={cerrarSesion}>Cerrar sesión</button>
    </main>
  );
}
