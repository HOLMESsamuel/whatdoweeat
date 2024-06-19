import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    vue(), 
    VitePWA({ 
      registerType: 'autoUpdate',
      manifest: {
        name: 'Whatdoweeat',
        short_name: 'Whatdoweeat',
        description: 'Find out what you are eating',
        theme_color: '#ffffff',
        icons: [
          {
            "src": "/android-chrome-192x192.png",
            "sizes": "192x192",
            "type": "image/png"
          },
          {
              "src": "/android-chrome-512x512.png",
              "sizes": "512x512",
              "type": "image/png"
          }
        ]
      }
     })],
});
