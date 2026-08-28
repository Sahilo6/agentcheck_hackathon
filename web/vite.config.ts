import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Relative asset paths, so the build works from a repository subpath on
  // GitHub Pages as well as from the filesystem during the demo.
  base: "./",
  // The fixture is ~1.5MB of JSON bundled straight in, so the app needs no
  // server and works with the wifi off. That is a demo requirement, not an
  // optimisation choice.
  build: { chunkSizeWarningLimit: 3000 },
});
