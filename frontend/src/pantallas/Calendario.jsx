import { useEffect, useMemo, useRef, useState } from "react";
import Cargando from "../componentes/Cargando.jsx";
import AusenciaVarios from "../componentes/AusenciaVarios.jsx";
import DetalleTurno from "../componentes/DetalleTurno.jsx";
import TarjetaTurno from "../componentes/TarjetaTurno.jsx";
import {
  agruparPorDia, diasDeSemana, etiquetaDia, etiquetaSemana, fechaLocal, lunesDe, sumarDias,
} from "../lib/fechas.js";
import { ESTADOS } from "../lib/semaforo.js";
import { useSesion } from "../sesion/useSesion.js";
import { useVacantesSimuladas } from "../simulado/useVacantesSimuladas.js";
import { useAusencias } from "./useAusencias.js";
import { useTurnosSemana } from "./useTurnosSemana.js";

export default function Calendario() {
  const { api, usuario, recargar, cerrarSesion } = useSesion();
  const [ahora, setAhora] = useState(null);
  const [lunes, setLunes] = useState(null);

  // "Hoy" sale del reloj del servidor (D27): el reloj de demo también mueve el calendario.
  useEffect(() => {
    let vigente = true;
    api
      .get("/api/health")
      .then((salud) => (Number.isNaN(Date.parse(salud?.ahora)) ? new Date().toISOString() : salud.ahora))
      .catch(() => new Date().toISOString())
      .then((instante) => {
        if (!vigente) return;
        setAhora(instante);
        setLunes(lunesDe(fechaLocal(instante)));
      });
    return () => {
      vigente = false;
    };
  }, [api]);

  if (lunes === null) return <Cargando texto="Cargando el calendario…" />;
  return <Semana api={api} usuario={usuario} ahora={ahora} lunes={lunes} setLunes={setLunes} recargar={recargar} cerrarSesion={cerrarSesion} />;
}

function Semana({ api, usuario, ahora, lunes, setLunes, recargar, cerrarSesion }) {
  const { estado, turnos, error, reintentar, refrescar } = useTurnosSemana(api, lunes, { alCuentaCambiada: recargar });
  const dias = useMemo(() => diasDeSemana(lunes), [lunes]);
  const porDia = useMemo(() => agruparPorDia(turnos, dias), [turnos, dias]);
  const visibles = dias.reduce((total, dia) => total + porDia[dia].length, 0);
  const hoy = fechaLocal(ahora);
  const ausencias = useAusencias(api, usuario);
  const simulado = useVacantesSimuladas({ usuario, ahora, reales: ausencias.abiertas });
  const acciones = { ...simulado, avisarAusencia: ausencias.avisar, retirarAviso: ausencias.retirar };
  const [seleccionado, setSeleccionado] = useState(null);
  const [variasFechas, setVariasFechas] = useState(false);
  useEffect(() => setSeleccionado(null), [lunes]);
  // El semáforo sale de la vacante que trae GET /api/turnos: al avisar o retirar una ausencia, se vuelve a pedir.
  const primeraVez = useRef(true);
  useEffect(() => {
    if (primeraVez.current) primeraVez.current = false;
    else refrescar();
  }, [ausencias.abiertas, refrescar]);

  return (
    <main className="calendario">
      <header className="cabecera">
        <div>
          <h2>{etiquetaSemana(lunes)}</h2>
          <p className="chico">{usuario.nombre}</p>
        </div>
        <button type="button" className="secundario" onClick={cerrarSesion}>Cerrar sesión</button>
      </header>
      <nav className="navegacion" aria-label="Semana">
        <button type="button" onClick={() => setLunes(sumarDias(lunes, -7))}>Semana anterior</button>
        <button type="button" className="secundario" onClick={() => setLunes(lunesDe(hoy))}>Hoy</button>
        <button type="button" onClick={() => setLunes(sumarDias(lunes, 7))}>Semana siguiente</button>
      </nav>
      <div className="barra">
        <button type="button" className="secundario" onClick={() => setVariasFechas(true)}>Avisar ausencia en varias fechas</button>
      </div>
      <ul className="leyenda" aria-label="Colores del calendario">
        {ESTADOS.map(({ clase, nombre }) => (
          <li key={clase} className={clase}>{nombre}</li>
        ))}
      </ul>
      {estado === "cargando" && <Cargando />}
      {estado === "error" && (
        <div>
          <p role="alert" className="error">{error.message}</p>
          <button type="button" onClick={reintentar}>Reintentar</button>
        </div>
      )}
      {estado === "ok" && visibles === 0 && <p className="vacio">No hay guardias esta semana.</p>}
      {estado === "ok" && (
        <div className="semana">
          {dias.map((dia) => (
            <section key={dia} className="dia" data-fecha={dia} aria-current={dia === hoy ? "date" : undefined}>
              <h3>{etiquetaDia(dia)}</h3>
              {porDia[dia].map((turno) => (
                <TarjetaTurno key={turno.id} turno={turno} usuario={usuario} onAbrir={setSeleccionado} />
              ))}
            </section>
          ))}
        </div>
      )}
      {seleccionado && (
        <DetalleTurno
          turno={seleccionado}
          estado={simulado.estadoDe(seleccionado)}
          acciones={acciones}
          onCerrar={() => setSeleccionado(null)}
        />
      )}
      {variasFechas && (
        <AusenciaVarios api={api} usuario={usuario} ahora={ahora} ausencias={ausencias} onCerrar={() => setVariasFechas(false)} />
      )}
    </main>
  );
}
