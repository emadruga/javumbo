import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  // Vite loads .env variables into process.env based on mode
  const appBasePath = process.env.VITE_APP_BASE_PATH || '/';

  return {
    plugins: [react()],
    // Use the environment variable for the base path
    base: appBasePath,
  };
});
