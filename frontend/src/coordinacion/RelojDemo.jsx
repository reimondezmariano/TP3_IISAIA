import { useEffect, useState } from "react";
import { ErrorApi } from "../lib/api.js";
import { fechaLocal, horaLocal } from "../lib/fechas.js";

const ADELANTOS = [
  { nombre: "+1 hora", horas: 1 },
  { nombre: "+1 día", horas: 24 },
];

// Reloj de demo (D27), solo para coordinadores. La ruta existe únicamente en modo demo: se la sondea con un cuerpo
// inválido, que no cambia nada (fuera de modo demo responde 404; en modo demo, 422) y el control aparece solo si existe.
export default function RelojDemo({ api, ahora, onCambio }) {
  const [disponible, setDisponible] = useState(false);
  const [haciendo, setHaciendo] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let vigente = true;
    api
      .post("/api/demo/reloj", {})
      .then(() => vigente && setDisponible(true))
      .catch((e) => vigente && setDisponible(e instanceof ErrorApi && e.status === 422));
    return () => {
      vigente = false;
    };
  }, [api]);

  if (!disponible) return null;

  async function mover(nuevoAhora) {
    if (haciendo) return;
    setHaciendo(true);
    setError(null);
    try {
      const reloj = await api.post("/api/demo/reloj", { ahora: nuevoAhora });
      await onCambio(reloj.ahora);
    } catch (e) {
      setError(e.message);
    } finally {
      setHaciendo(false);
    }
  }

  return (
    <section className="reloj-demo" aria-label="Reloj de demo">
      <p className="chico">Reloj de demo: {fechaLocal(ahora)} {horaLocal(ahora)}</p>
      <div className="barra">
        {ADELANTOS.map(({ nombre, horas }) => (
          <button key={nombre} type="button" className="secundario" disabled={haciendo} onClick={() => mover(new Date(new Date(ahora).getTime() + horas * 3_600_000).toISOString())}>
            {nombre}
          </button>
        ))}
        <button type="button" className="secundario" disabled={haciendo} onClick={() => mover(null)}>Volver a la hora real</button>
      </div>
      {error && <p role="alert" className="error">{error}</p>}
    </section>
  );
}
