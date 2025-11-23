import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  // Vite loads .env variables into process.env based on mode
  const appBasePath = env.VITE_APP_BASE_PATH || '/';
  // --- Add this log ---
  console.log(`[vite.config.js] Mode: ${mode}, VITE_APP_BASE_PATH: ${process.env.VITE_APP_BASE_PATH}, Using base: ${appBasePath}`);
  // --------------------

  return {
    plugins: [react()],
    // Use the environment variable for the base path
    base: appBasePath,
  };
});
