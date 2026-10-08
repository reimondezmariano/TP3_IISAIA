import "./coordinacion.css";
import { useEffect, useState } from "react";
import { asignar, candidatosDe, marcarSinCobertura } from "../lib/cobertura.js";

const MOTIVOS = {
  ES_TITULAR: "es el titular del turno",
  GUARDIA_SUPERPUESTA: "tiene otra guardia superpuesta",
};

const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;

// Panel del coordinador dentro del detalle de un turno: candidatos ordenados por equidad (D17), asignación
// directa o reasignación (D18) y marca de sin cobertura (D19). El servidor valida todo; acá solo se muestra.
export default function PanelCobertura({ api, turnoId, alCambiar = () => {} }) {
  const [candidatos, setCandidatos] = useState({ estado: "cargando", datos: null, error: null });
  const [medicos, setMedicos] = useState([]);
  const [elegido, setElegido] = useState("");
  const [haciendo, setHaciendo] = useState(false);
  const [aviso, setAviso] = useState(null);
  const [error, setError] = useState(null);
  const [aReasignar, setAReasignar] = useState(null);

  useEffect(() => {
    let vigente = true;
    candidatosDe(api, turnoId)
      .then((datos) => vigente && setCandidatos({ estado: "ok", datos, error: null }))
      .catch((e) => vigente && setCandidatos({ estado: "error", datos: null, error: e }));
    api
      .get("/api/usuarios")
      .then((usuarios) => vigente && setMedicos(usuarios.filter((u) => u.rol === "MEDICO" && u.estado === "ACTIVO")))
      .catch(() => {}); // sin la lista solo falta la asignación directa; los candidatos siguen
    return () => {
      vigente = false;
    };
  }, [api, turnoId]);

  async function ejecutar(accion) {
    if (haciendo) return;
    setHaciendo(true);
    setError(null);
    setAviso(null);
    setAReasignar(null);
    try {
      await accion();
    } catch (e) {
      setError(e.message);
      return e;
    } finally {
      setHaciendo(false);
    }
  }

  async function asignarA(medico, reasignar = false) {
    const fallo = await ejecutar(async () => {
      const resultado = await asignar(api, turnoId, medico.id, reasignar);
      setAviso(`${resultado.asignado.nombre} cubre este turno.`);
      await alCambiar();
    });
    if (fallo?.codigo === "YA_TIENE_ASIGNADO") setAReasignar(medico);
  }

  const sinCobertura = () =>
    ejecutar(async () => {
      await marcarSinCobertura(api, turnoId);
      setAviso("El turno quedó marcado sin cobertura.");
      await alCambiar();
    });

  const elegible = (id) => medicos.find((m) => m.id === Number(id));

  return (
    <section className="cobertura" aria-label="Cobertura del turno">
      <h3>Cobertura</h3>
      {candidatos.estado === "cargando" && <p className="chico">Cargando candidatos…</p>}
      {candidatos.estado === "error" && <p role="alert" className="error">{candidatos.error.message}</p>}
      {candidatos.estado === "ok" && (
        <>
          <p className="chico">Orden por equidad: primero quien cubrió menos en el mes ({candidatos.datos.mes}). Las horas de la semana son un dato, no ordenan.</p>
          {candidatos.datos.candidatos.length === 0 && <p className="vacio">Nadie se postuló todavía.</p>}
          <ol className="candidatos">
            {candidatos.datos.candidatos.map((c) => (
              <li key={c.medico.id} data-testid="candidato" className={c.elegible ? undefined : "no-elegible"}>
                <strong data-testid="candidato-nombre">{c.medico.nombre}</strong>
                <span className="chico">
                  {plural(c.coberturasMes, "cobertura", "coberturas")} en el mes · {c.horasSemana} h esta semana
                </span>
                {c.elegible ? (
                  <button type="button" disabled={haciendo} onClick={() => asignarA(c.medico)}>Elegir</button>
                ) : (
                  <span className="chico">No elegible: {MOTIVOS[c.motivoInelegibilidad] ?? c.motivoInelegibilidad}</span>
                )}
              </li>
            ))}
          </ol>
        </>
      )}
      <label>
        Asignar directamente a
        <select value={elegido} onChange={(e) => setElegido(e.target.value)}>
          <option value="">Elegí un médico</option>
          {medicos.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}
        </select>
      </label>
      <button type="button" disabled={haciendo || !elegible(elegido)} onClick={() => asignarA(elegible(elegido))}>Asignar</button>
      {aReasignar && (
        <button type="button" disabled={haciendo} onClick={() => asignarA(aReasignar, true)}>Reasignar a {aReasignar.nombre}</button>
      )}
      <button type="button" className="secundario" disabled={haciendo} onClick={sinCobertura}>Marcar sin cobertura</button>
      {aviso && <p role="status">{aviso}</p>}
      {error && <p role="alert" className="error">{error}</p>}
    </section>
  );
}
