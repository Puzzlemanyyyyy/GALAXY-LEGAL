import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: true,
    // Allow Emergent preview hostnames; Vite blocks unknown hosts by default
    // when accessed through HTTPS reverse proxy.
    allowedHosts: true,
    hmr: {
      clientPort: 443,
      protocol: 'wss',
    },
  },
  preview: { host: '0.0.0.0', port: parseInt(process.env.PORT || '4173') },
})
