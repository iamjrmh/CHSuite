import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { ToastProvider } from "./components/Toast";
import { ConfigProvider } from "./lib/config-context";
import { UpdateProvider } from "./lib/update-context";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider>
      <ToastProvider>
        <UpdateProvider>
          <App />
        </UpdateProvider>
      </ToastProvider>
    </ConfigProvider>
  </React.StrictMode>,
);
