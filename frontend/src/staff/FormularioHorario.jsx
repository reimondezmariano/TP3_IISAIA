import { useState } from "react";
import { useEnvio } from "../pantallas/useEnvio.js";
import { hhmm, nombreDia } from "./formato.js";

const DIAS = [1, 2, 3, 4, 5, 6, 7];

// Alta de un horario (modo "crear") o nueva versión de uno existente (modo "modificar"). En "modificar"
// solo se mandan los campos que cambiaron (el servidor copia el resto de la versión que rige).
export default function FormularioHorario({ modo, medicos, inicial, desdePorDefecto, onEnviar, onCancelar }) {
  const crear = modo === "crear";
  const [medicoId, setMedicoId] = useState(inicial?.medico ? String(inicial.medico.id) : "");
  const [diaSemana, setDiaSemana] = useState(String(inicial?.diaSemana ?? 1));
  const [horaInicio, setHoraInicio] = useState(inicial ? hhmm(inicial.horaInicio) : "08:00");
  const [duracionHoras, setDuracionHoras] = useState(String(inicial?.duracionHoras ?? 12));
  const [frecuenciaSemanas, setFrecuenciaSemanas] = useState(String(inicial?.frecuenciaSemanas ?? 1));
  const [desde, setDesde] = useState(desdePorDefecto);

  const { enviando, error, enviar } = useEnvio(async () => {
    if (!desde) throw new Error("Elegí desde qué fecha rige.");
    if (crear && !medicoId) throw new Error("Elegí el médico titular.");
    const valores = {
      diaSemana: Number(diaSemana),
      horaInicio,
      duracionHoras: Number(duracionHoras),
      frecuenciaSemanas: Number(frecuenciaSemanas),
    };
    if (crear) {
      await onEnviar({ medicoId: Number(medicoId), ...valores, vigenteDesde: desde });
      return;
    }
    const cambios = {};
    if (valores.diaSemana !== inicial.diaSemana) cambios.diaSemana = valores.diaSemana;
    if (valores.horaInicio !== hhmm(inicial.horaInicio)) cambios.horaInicio = valores.horaInicio;
    if (valores.duracionHoras !== inicial.duracionHoras) cambios.duracionHoras = valores.duracionHoras;
    if (valores.frecuenciaSemanas !== inicial.frecuenciaSemanas) cambios.frecuenciaSemanas = valores.frecuenciaSemanas;
    if (medicoId && Number(medicoId) !== inicial.medico?.id) cambios.medicoId = Number(medicoId);
    if (Object.keys(cambios).length === 0) throw new Error("No cambiaste nada.");
    await onEnviar({ desde, ...cambios });
  });

  return (
    <form onSubmit={enviar} className="formulario-horario" noValidate>
      <label>
        Médico titular
        <select value={medicoId} onChange={(e) => setMedicoId(e.target.value)}>
          <option value="">{crear ? "Elegí un médico" : "Sin cambios"}</option>
          {medicos.map((m) => (
            <option key={m.id} value={m.id}>{m.nombre}</option>
          ))}
        </select>
      </label>
      <label>
        Día
        <select value={diaSemana} onChange={(e) => setDiaSemana(e.target.value)}>
          {DIAS.map((d) => (
            <option key={d} value={d}>{nombreDia(d)}</option>
          ))}
        </select>
      </label>
      <label>
        Hora de inicio
        <input type="time" value={horaInicio} onChange={(e) => setHoraInicio(e.target.value)} required />
      </label>
      <label>
        Duración (horas)
        <input type="number" min="1" max="24" value={duracionHoras} onChange={(e) => setDuracionHoras(e.target.value)} />
      </label>
      <label>
        Frecuencia (cada cuántas semanas)
        <input type="number" min="1" max="52" value={frecuenciaSemanas} onChange={(e) => setFrecuenciaSemanas(e.target.value)} />
        <small>1 es todas las semanas; 2, semana por medio.</small>
      </label>
      <label>
        {crear ? "Rige desde" : "Cambio desde"}
        <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} />
      </label>
      {error && <p role="alert" className="error">{error}</p>}
      <div className="acciones">
        <button type="submit" disabled={enviando}>{enviando ? "Guardando…" : crear ? "Cargar horario" : "Guardar cambio"}</button>
        {onCancelar && <button type="button" className="secundario" onClick={onCancelar}>Cancelar</button>}
      </div>
    </form>
  );
}
