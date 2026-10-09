import { useEffect, useMemo, useState } from "react";
import IndicadorSinCobertura from "../coordinacion/IndicadorSinCobertura.jsx";
import RelojDemo from "../coordinacion/RelojDemo.jsx";
import PanelCobertura from "../coordinacion/PanelCobertura.jsx";
import Cargando from "../componentes/Cargando.jsx";
import AusenciaVarios from "../componentes/AusenciaVarios.jsx";
import DetalleTurno from "../componentes/DetalleTurno.jsx";
import MesCalendario from "../componentes/MesCalendario.jsx";
import TarjetaTurno from "../componentes/TarjetaTurno.jsx";
import {
  MESES, agruparPorDia, diasDeSemana, etiquetaDia, etiquetaMes, etiquetaSemana, fechaLocal, lunesDe, mesDe, rangoMes, sumarDias, sumarMeses,
} from "../lib/fechas.js";
import { ESTADOS } from "../lib/semaforo.js";
import { useSesion } from "../sesion/useSesion.js";
import { derivarEstado } from "../lib/estadoTurno.js";
import { useAusencias } from "./useAusencias.js";
import { usePostulaciones } from "./usePostulaciones.js";
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
  return <Semana api={api} usuario={usuario} ahora={ahora} setAhora={setAhora} lunes={lunes} setLunes={setLunes} recargar={recargar} cerrarSesion={cerrarSesion} />;
}

function Semana({ api, usuario, ahora, setAhora, lunes, setLunes, recargar, cerrarSesion }) {
  const hoy = fechaLocal(ahora);
  const [vista, setVista] = useState("semana");
  const [mes, setMes] = useState(mesDe(hoy));
  const esMes = vista === "mes";
  // En la vista mensual se pide la grilla completa (de lunes a domingo, con días de los meses vecinos).
  const rango = esMes ? rangoMes(mes) : null;
  const { estado, turnos, error, reintentar, refrescar } = useTurnosSemana(api, esMes ? rango.desde : lunes, {
    alCuentaCambiada: recargar, hasta: esMes ? rango.hasta : null,
  });
  const dias = useMemo(() => diasDeSemana(lunes), [lunes]);
  const porDia = useMemo(() => agruparPorDia(turnos, dias), [turnos, dias]);
  const visibles = esMes ? turnos.length : dias.reduce((total, dia) => total + porDia[dia].length, 0);
  const cambiarVista = (nueva) => {
    if (nueva === "mes") setMes(mesDe(lunes <= hoy && hoy <= sumarDias(lunes, 6) ? hoy : sumarDias(lunes, 3)));
    else setLunes(lunesDe(mesDe(hoy) === mes ? hoy : `${mes}-01`));
    setVista(nueva);
  };
  const [anioMes, numeroMes] = mes.split("-").map(Number);
  const anios = Array.from({ length: 11 }, (_, i) => anioMes - 5 + i);
  const irAMes = (anio, numero) => setMes(`${anio}-${String(numero).padStart(2, "0")}`);
  const ausencias = useAusencias(api, usuario, { alCambiar: refrescar });
  const postulaciones = usePostulaciones(api, { alCambiar: refrescar });
  const estadoDe = (turno) =>
    derivarEstado({ turno, usuario, ahora });
  const acciones = {
    avisarAusencia: ausencias.avisar, retirarAviso: ausencias.retirar,
    postularme: postulaciones.postular, retirarPostulacion: postulaciones.retirar,
  };
  // Se guarda el id y se busca en la lista vigente: al recargar, el detalle muestra la vacante nueva.
  const [seleccionadoId, setSeleccionadoId] = useState(null);
  const seleccionado = turnos.find((t) => t.id === seleccionadoId) ?? null;
  // El panel de cobertura solo se pide para turnos con vacante o BAJA, y se mantiene abierto aunque la acción
  // cierre la vacante (así sigue visible el resultado). `version` vuelve a pedir el indicador del mes.
  const [panelPara, setPanelPara] = useState(null);
  const [version, setVersion] = useState(0);
  const abrir = (t) => {
    setSeleccionadoId(t.id);
    setPanelPara(t.vacante || t.titular === null ? t.id : null);
  };
  const estadoSel = seleccionado ? estadoDe(seleccionado) : null;
  const verPanel = seleccionado && usuario.rol === "COORDINADOR" && estadoSel.tipo !== "PASADO" &&
    (panelPara === seleccionado.id || seleccionado.vacante || seleccionado.titular === null);
  const trasCobertura = async () => {
    await refrescar();
    setVersion((v) => v + 1);
  };
  // Con otro "ahora" cambian el semáforo, las acciones y el indicador del mes: se vuelve a pedir todo.
  const cambioElReloj = async (nuevoAhora) => {
    setAhora(nuevoAhora);
    await refrescar();
    setVersion((v) => v + 1);
  };
  const [variasFechas, setVariasFechas] = useState(false);
  useEffect(() => setSeleccionadoId(null), [lunes, mes, vista]);

  return (
    <main className="calendario">
      <header className="cabecera">
        <div>
          <h2>{esMes ? etiquetaMes(mes) : etiquetaSemana(lunes)}</h2>
          <p className="chico">{usuario.nombre}</p>
        </div>
        <button type="button" className="secundario" onClick={cerrarSesion}>Cerrar sesión</button>
      </header>
      {usuario.rol === "COORDINADOR" && <IndicadorSinCobertura key={version} api={api} ahora={ahora} />}
      {usuario.rol === "COORDINADOR" && <RelojDemo api={api} ahora={ahora} onCambio={cambioElReloj} />}
      <div className="vistas" role="group" aria-label="Vista del calendario">
        <button type="button" className="secundario" aria-pressed={!esMes} onClick={() => cambiarVista("semana")}>Semana</button>
        <button type="button" className="secundario" aria-pressed={esMes} onClick={() => cambiarVista("mes")}>Mes</button>
      </div>
      {esMes ? (
        <>
          <nav className="navegacion" aria-label="Mes">
            <button type="button" onClick={() => setMes(sumarMeses(mes, -1))}>Mes anterior</button>
            <button type="button" className="secundario" onClick={() => setMes(mesDe(hoy))}>Hoy</button>
            <button type="button" onClick={() => setMes(sumarMeses(mes, 1))}>Mes siguiente</button>
          </nav>
          <div className="selector-mes">
            <label>
              Mes
              <select value={numeroMes} onChange={(e) => irAMes(anioMes, Number(e.target.value))}>
                {MESES.map((nombre, i) => (
                  <option key={nombre} value={i + 1}>{nombre}</option>
                ))}
              </select>
            </label>
            <label>
              Año
              <select value={anioMes} onChange={(e) => irAMes(Number(e.target.value), numeroMes)}>
                {anios.map((anio) => (
                  <option key={anio} value={anio}>{anio}</option>
                ))}
              </select>
            </label>
          </div>
        </>
      ) : (
        <nav className="navegacion" aria-label="Semana">
          <button type="button" onClick={() => setLunes(sumarDias(lunes, -7))}>Semana anterior</button>
          <button type="button" className="secundario" onClick={() => setLunes(lunesDe(hoy))}>Hoy</button>
          <button type="button" onClick={() => setLunes(sumarDias(lunes, 7))}>Semana siguiente</button>
        </nav>
      )}
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
      {estado === "ok" && visibles === 0 && <p className="vacio">No hay guardias {esMes ? "este mes" : "esta semana"}.</p>}
      {estado === "ok" && esMes && <MesCalendario mes={mes} turnos={turnos} hoy={hoy} onAbrir={abrir} />}
      {estado === "ok" && !esMes && (
        <div className="semana">
          {dias.map((dia) => (
            <section key={dia} className="dia" data-fecha={dia} aria-current={dia === hoy ? "date" : undefined}>
              <h3>{etiquetaDia(dia)}</h3>
              {porDia[dia].map((turno) => (
                <TarjetaTurno key={turno.id} turno={turno} usuario={usuario} onAbrir={abrir} />
              ))}
            </section>
          ))}
        </div>
      )}
      {seleccionado && (
        <DetalleTurno
          turno={seleccionado}
          estado={estadoSel}
          acciones={acciones}
          panel={verPanel ? <PanelCobertura api={api} turnoId={seleccionado.id} alCambiar={trasCobertura} /> : null}
          onCerrar={() => setSeleccionadoId(null)}
        />
      )}
      {variasFechas && (
        <AusenciaVarios api={api} usuario={usuario} ahora={ahora} ausencias={ausencias} onCerrar={() => setVariasFechas(false)} />
      )}
    </main>
  );
}
