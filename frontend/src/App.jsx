import { useEffect, useState } from "react";

export default function App() {
  const [salud, setSalud] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("/api/health")
      .then(async (respuesta) => {
        const cuerpo = await respuesta.json().catch(() => ({}));
        if (!respuesta.ok) throw new Error(cuerpo.mensaje ?? `Error ${respuesta.status}`);
        setSalud(cuerpo);
      })
      .catch((e) => setError(e.message));
  }, []);

  return (
    <main>
      <h1>Guardia Viva</h1>
      {error && <p role="alert">No se pudo consultar el servidor: {error}</p>}
      {!salud && !error && <p>Consultando el servidor…</p>}
      {salud && (
        <dl>
          <dt>Estado</dt>
          <dd data-testid="estado">{salud.estado}</dd>
          <dt>Base de datos</dt>
          <dd data-testid="base">{salud.base}</dd>
          <dt>Hora del servidor</dt>
          <dd data-testid="ahora">{salud.ahora}</dd>
        </dl>
      )}
    </main>
  );
}
