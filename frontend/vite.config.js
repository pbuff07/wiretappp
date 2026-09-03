import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig(({ mode }) => ({
  plugins: [vue()],
  base: mode === "production" ? "./" : "/",
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:18760",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
}));
