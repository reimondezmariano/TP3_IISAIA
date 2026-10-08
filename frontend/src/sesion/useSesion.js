import { createContext, useContext } from "react";

export const ContextoSesion = createContext(null);

export function useSesion() {
  const contexto = useContext(ContextoSesion);
  if (!contexto) throw new Error("useSesion se usa dentro de <SesionProvider>.");
  return contexto;
}
