import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App";
import "./styles/index.css";

const root = document.getElementById("root");

if (root === null) {
  throw new Error("APP_ROOT_MISSING");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
