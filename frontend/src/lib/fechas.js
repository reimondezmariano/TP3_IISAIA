export const ZONA = "America/Argentina/Buenos_Aires";

const formatoFecha = new Intl.DateTimeFormat("en-CA", { timeZone: ZONA, year: "numeric", month: "2-digit", day: "2-digit" });
const formatoHora = new Intl.DateTimeFormat("es-AR", { timeZone: ZONA, hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const DIAS = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];

export function fechaLocal(instante) {
  return formatoFecha.format(new Date(instante));
}

export function horaLocal(instante) {
  return formatoHora.format(new Date(instante));
}

// Las fechas calendario se manejan como UTC a medianoche solo para hacer cuentas de días; no son instantes.
function aUtc(fecha) {
  const [anio, mes, dia] = fecha.split("-").map(Number);
  return new Date(Date.UTC(anio, mes - 1, dia));
}

function deUtc(date) {
  return date.toISOString().slice(0, 10);
}

export function sumarDias(fecha, n) {
  const date = aUtc(fecha);
  date.setUTCDate(date.getUTCDate() + n);
  return deUtc(date);
}

export function lunesDe(fecha) {
  const diaSemana = aUtc(fecha).getUTCDay(); // 0 = domingo
  return sumarDias(fecha, -((diaSemana + 6) % 7));
}

export function diasDeSemana(lunes) {
  return Array.from({ length: 7 }, (_, i) => sumarDias(lunes, i));
}

export function rangoSemana(lunes) {
  return { desde: lunes, hasta: sumarDias(lunes, 6) };
}

export function agruparPorDia(turnos, dias) {
  const grupos = Object.fromEntries(dias.map((dia) => [dia, []]));
  for (const turno of turnos) {
    if (turno.fecha in grupos) grupos[turno.fecha].push(turno);
  }
  for (const lista of Object.values(grupos)) {
    lista.sort((a, b) => new Date(a.inicio) - new Date(b.inicio));
  }
  return grupos;
}

export function etiquetaDia(fecha) {
  const date = aUtc(fecha);
  return `${DIAS[date.getUTCDay()]} ${date.getUTCDate()}`;
}

export function etiquetaSemana(lunes) {
  const a = aUtc(lunes);
  const b = aUtc(sumarDias(lunes, 6));
  const mismoMes = a.getUTCMonth() === b.getUTCMonth();
  const mismoAnio = a.getUTCFullYear() === b.getUTCFullYear();
  const izquierda = mismoMes ? `${a.getUTCDate()}` : `${a.getUTCDate()} de ${MESES[a.getUTCMonth()]}${mismoAnio ? "" : ` de ${a.getUTCFullYear()}`}`;
  return `${izquierda} al ${b.getUTCDate()} de ${MESES[b.getUTCMonth()]} de ${b.getUTCFullYear()}`;
}

export function terminoAntes(turno, ahora) {
  return new Date(turno.fin) < new Date(ahora);
}

export function horasHasta(turno, ahora) {
  return (new Date(turno.inicio) - new Date(ahora)) / 3_600_000;
}
