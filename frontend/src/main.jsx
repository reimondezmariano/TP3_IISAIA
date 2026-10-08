import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { registrarServiceWorker } from "./lib/pwa.js";
import { crearAuthSupabase } from "./lib/supabase.js";
import { SesionProvider } from "./sesion/SesionProvider.jsx";
import "./estilos.css";

function raiz() {
  try {
    const auth = crearAuthSupabase();
    return (
      <SesionProvider auth={auth}>
        <App />
      </SesionProvider>
    );
  } catch (error) {
    return <p role="alert" className="error">{error.message}</p>;
  }
}

createRoot(document.getElementById("root")).render(<StrictMode>{raiz()}</StrictMode>);

registrarServiceWorker();
