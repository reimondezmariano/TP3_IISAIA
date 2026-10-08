import { useState } from "react";
import { etiquetaDia, fechaLocal, horaLocal, sumarDias } from "../lib/fechas.js";
import { useEnvio } from "../pantallas/useEnvio.js";

const MAX_DIAS = 62; // tope de GET /api/turnos
const MAX_LOTE = 31; // tope de POST /api/vacantes/lote

// Avisar la ausencia en varias fechas de una vez (D15). El médico elige entre sus guardias que todavía no
// empezaron; el coordinador, entre todas las del rango.
export default function AusenciaVarios({ api, usuario, ahora, ausencias, onCerrar, onCambio }) {
  const hoy = fechaLocal(ahora);
  const esCoordinador = usuario.rol === "COORDINADOR";
  const [desde, setDesde] = useState(hoy);
  const [hasta, setHasta] = useState(sumarDias(hoy, 6));
  const [turnos, setTurnos] = useState(null);
  const [elegidos, setElegidos] = useState([]);
  const [motivo, setMotivo] = useState("");
  const [resumen, setResumen] = useState(null);

  const buscar = useEnvio(async () => {
    setResumen(null);
    if (!desde || !hasta || hasta < desde) throw new Error("Elegí un rango de fechas válido.");
    if (sumarDias(desde, MAX_DIAS - 1) < hasta) throw new Error(`El rango no puede superar ${MAX_DIAS} días.`);
    const todos = await api.get("/api/turnos", { desde, hasta });
    const mios = todos.filter(
      (t) =>
        new Date(t.inicio) > new Date(ahora) &&
        t.fecha >= desde &&
        t.fecha <= hasta &&
        (esCoordinador ? t.titular !== null : t.titular?.id === usuario.id) &&
        t.vacante == null,
    );
    setTurnos(mios);
    setElegidos(mios.slice(0, MAX_LOTE).map((t) => t.id));
  });

  const enviar = useEnvio(async () => {
    if (elegidos.length === 0) throw new Error("Elegí al menos una guardia.");
    if (!motivo.trim()) throw new Error("Escribí el motivo de la ausencia.");
    if (esCoordinador && elegidos.length > MAX_LOTE) throw new Error(`Se pueden avisar hasta ${MAX_LOTE} fechas a la vez.`);
    const resultado = await ausencias.avisarVarios(elegidos, motivo.trim());
    setResumen(resultado);
    setTurnos((actuales) => actuales.filter((t) => !resultado.ok.includes(t.id)));
    setElegidos(resultado.fallaron.map((f) => f.turnoId));
    onCambio?.();
  });

  const alternar = (id) => setElegidos((previos) => (previos.includes(id) ? previos.filter((x) => x !== id) : [...previos, id]));

  return (
    <div className="detalle-fondo">
      <section className="detalle" role="dialog" aria-modal="true" aria-labelledby="varios-titulo">
        <h2 id="varios-titulo">Avisar ausencia en varias fechas</h2>
        <form onSubmit={buscar.enviar} noValidate>
          <label>
            Desde
            <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} />
          </label>
          <label>
            Hasta
            <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} />
          </label>
          <button type="submit" className="secundario" disabled={buscar.enviando}>
            {buscar.enviando ? "Buscando…" : esCoordinador ? "Buscar guardias" : "Buscar mis guardias"}
          </button>
          {buscar.error && <p role="alert" className="error">{buscar.error}</p>}
        </form>
        {turnos !== null && turnos.length === 0 && !resumen && <p className="vacio">No hay guardias para avisar en ese rango.</p>}
        {turnos !== null && turnos.length > 0 && (
          <form onSubmit={enviar.enviar} noValidate>
            <fieldset className="lista-elegir">
              <legend>Guardias</legend>
              {turnos.map((t) => (
                <label key={t.id} className="elegir">
                  <input type="checkbox" checked={elegidos.includes(t.id)} onChange={() => alternar(t.id)} />
                  <span>
                    {etiquetaDia(t.fecha)} · {horaLocal(t.inicio)} – {horaLocal(t.fin)}
                    {esCoordinador && t.titular ? ` · ${t.titular.nombre}` : ""}
                  </span>
                </label>
              ))}
            </fieldset>
            <label>
              Motivo (solo lo ven los coordinadores)
              <input value={motivo} onChange={(e) => setMotivo(e.target.value)} maxLength={500} />
            </label>
            {enviar.error && <p role="alert" className="error">{enviar.error}</p>}
            <button type="submit" disabled={enviar.enviando}>
              {enviar.enviando ? "Enviando…" : `Avisar ${elegidos.length} ${elegidos.length === 1 ? "fecha" : "fechas"}`}
            </button>
          </form>
        )}
        {resumen && (
          <div role="status">
            {resumen.ok.length > 0 && <p className="ok">Se avisó la ausencia en {resumen.ok.length} {resumen.ok.length === 1 ? "fecha" : "fechas"}.</p>}
            {resumen.fallaron.length > 0 && (
              <div className="error">
                <p>No se pudo avisar en {resumen.fallaron.length} {resumen.fallaron.length === 1 ? "fecha" : "fechas"}:</p>
                <ul>
                  {resumen.fallaron.map((f) => (
                    <li key={f.turnoId}>{etiquetaDia(f.turnoId.split(":")[1])}: {f.mensaje}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
        <button type="button" className="secundario" onClick={onCerrar}>Cerrar</button>
      </section>
    </div>
  );
}
