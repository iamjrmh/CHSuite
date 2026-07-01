import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Tauri expects a fixed dev port and no clearing of the screen so its own
// logging stays visible. See https://tauri.app/start/frontend/vite/
const host = process.env.TAURI_DEV_HOST;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host
      ? { protocol: "ws", host, port: 1421 }
      : undefined,
    watch: {
      // Tauri's Rust sources are watched by Cargo, not Vite.
      ignored: ["**/src-tauri/**", "**/sidecar/**"],
    },
  },
  // Produce a relative-asset build so the frontend works when loaded from the
  // Tauri custom protocol (tauri://localhost).
  build: {
    target: "chrome105",
    minify: "esbuild",
    sourcemap: false,
  },
});
