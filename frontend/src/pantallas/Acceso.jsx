import { useState } from "react";
import { useSesion } from "../sesion/useSesion.js";
import { useEnvio } from "./useEnvio.js";

export default function Acceso() {
  const { iniciarSesion, registrarse, aviso } = useSesion();
  const [modo, setModo] = useState("ingresar");
  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [codigo, setCodigo] = useState("");

  const ingreso = modo === "ingresar";
  const { enviando, error, enviar } = useEnvio(async () => {
    if (ingreso) return iniciarSesion(email.trim(), password);
    if (password.length < 6) throw new Error("La contraseña debe tener al menos 6 caracteres.");
    return registrarse({ nombre, email: email.trim(), password, codigo });
  });

  return (
    <main className="acceso">
      <h1>Guardia Viva</h1>
      <div role="tablist" className="pestanas">
        <button role="tab" aria-selected={ingreso} onClick={() => setModo("ingresar")} type="button">Ingresar</button>
        <button role="tab" aria-selected={!ingreso} onClick={() => setModo("registrar")} type="button">Registrarme</button>
      </div>
      {aviso && <p role="status" className="aviso">{aviso}</p>}
      <form onSubmit={enviar}>
        {!ingreso && (
          <label>
            Nombre
            <input value={nombre} onChange={(e) => setNombre(e.target.value)} autoComplete="name" required maxLength={120} />
          </label>
        )}
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
        </label>
        <label>
          Contraseña
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={ingreso ? "current-password" : "new-password"}
            required
          />
        </label>
        {!ingreso && (
          <label>
            Código de coordinación (opcional)
            <input value={codigo} onChange={(e) => setCodigo(e.target.value)} autoComplete="off" maxLength={64} />
            <small>Solo para coordinadores. Si no lo tenés, dejalo vacío: un coordinador va a activar tu cuenta.</small>
          </label>
        )}
        {error && <p role="alert" className="error">{error}</p>}
        <button type="submit" disabled={enviando}>
          {ingreso ? (enviando ? "Ingresando…" : "Ingresar") : enviando ? "Creando cuenta…" : "Crear cuenta"}
        </button>
      </form>
    </main>
  );
}
