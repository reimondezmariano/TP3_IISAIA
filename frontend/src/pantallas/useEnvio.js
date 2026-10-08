import { useState } from "react";

// Maneja "enviando" y el error de un formulario; ignora envíos mientras hay uno en curso.
export function useEnvio(accion) {
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);
  async function enviar(evento) {
    evento.preventDefault();
    if (enviando) return;
    setEnviando(true);
    setError(null);
    try {
      await accion();
    } catch (e) {
      setError(e.message);
    } finally {
      setEnviando(false);
    }
  }
  return { enviando, error, enviar };
}
