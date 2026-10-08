export default function Cargando({ texto = "Cargando…" }) {
  return (
    <p className="cargando" role="status">
      {texto}
    </p>
  );
}
