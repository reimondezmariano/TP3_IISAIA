import { etiquetaDia, horaLocal } from "../lib/fechas.js";

const DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];

export const nombreDia = (n) => DIAS[n - 1] ?? "?";
export const hhmm = (hora) => String(hora).slice(0, 5);

export function describirHorario(h) {
  const cada = h.frecuenciaSemanas === 1 ? "todas las semanas" : `cada ${h.frecuenciaSemanas} semanas`;
  return `${nombreDia(h.diaSemana)} ${hhmm(h.horaInicio)} · ${h.duracionHoras} h · ${cada}`;
}

export const describirTurno = (t) =>
  `${etiquetaDia(t.fecha)} ${horaLocal(t.inicio)} – ${horaLocal(t.fin)}`;

// La versión que rige hoy o, si ninguna rige todavía, la próxima; null si el horario está cerrado.
export function versionActual(horario, hoy) {
  const ordenadas = [...horario.versiones].sort((a, b) => a.vigenteDesde.localeCompare(b.vigenteDesde));
  const rige = ordenadas.find((v) => v.vigenteDesde <= hoy && (v.vigenteHasta === null || hoy < v.vigenteHasta));
  return rige ?? ordenadas.find((v) => v.vigenteDesde > hoy) ?? null;
}
