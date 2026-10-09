import { agruparPorDia, etiquetaMes, fechaLocal, horaLocal, semanasDeMes } from "../lib/fechas.js";
import { quienCubre } from "../lib/quienCubre.js";
import { semaforo } from "../lib/semaforo.js";

const CABECERA = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"];

// Grilla del mes (lunes a domingo): cada día lista sus guardias compactas con los colores del semáforo (D08).
// En el celular cada guardia muestra solo la hora de inicio; el detalle completo se abre al tocarla.
export default function MesCalendario({ mes, turnos, hoy, onAbrir }) {
  const semanas = semanasDeMes(mes);
  const porDia = agruparPorDia(turnos, semanas.flat());
  return (
    <div className="mes" role="grid" aria-label={`Guardias de ${etiquetaMes(mes)}`}>
      <div className="mes-cabecera" role="row">
        {CABECERA.map((dia) => (
          <span key={dia} role="columnheader">{dia}</span>
        ))}
      </div>
      {semanas.map((dias) => (
        <div key={dias[0]} className="mes-semana" role="row">
          {dias.map((dia) => (
            <div
              key={dia}
              role="gridcell"
              className={`mes-dia${dia.startsWith(mes) ? "" : " fuera"}`}
              data-fecha={dia}
              aria-current={dia === hoy ? "date" : undefined}
            >
              <span className="mes-numero">{Number(dia.slice(8))}</span>
              {porDia[dia].map((turno) => (
                <ChipTurno key={turno.id} turno={turno} onAbrir={onAbrir} />
              ))}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function ChipTurno({ turno, onAbrir }) {
  const { clase, etiqueta } = semaforo(turno);
  const { principal } = quienCubre(turno);
  const hora = horaLocal(turno.inicio);
  const diaSiguiente = fechaLocal(turno.fin) !== turno.fecha;
  const descripcion = `${hora} a ${horaLocal(turno.fin)}${diaSiguiente ? " (+1 día)" : ""}, ${principal}${etiqueta ? `, ${etiqueta}` : ""}`;
  return (
    <button type="button" className={`turno-mes ${clase}`} data-testid="turno-mes" data-turno-id={turno.id} data-semaforo={clase} aria-label={descripcion} onClick={() => onAbrir(turno)}>
      <span className="turno-mes-hora">{hora}</span>
      <span className="turno-mes-nombre">{principal}</span>
    </button>
  );
}
