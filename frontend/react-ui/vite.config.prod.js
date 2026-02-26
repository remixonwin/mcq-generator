import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // Production build optimizations
    target: 'es2015',
    minify: 'terser',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          // Vendor chunk for third-party libraries
          vendor: ['react', 'react-dom', 'react-router-dom'],
          
          // React Query chunk
          query: ['@tanstack/react-query'],
          
          // UI library chunk
          ui: ['lucide-react'],
          
          // Utils chunk
          utils: ['axios'],
          
          // Component chunks (will be auto-detected)
          components: [
            './src/components',
            './src/pages'
          ]
        },
        chunkFileNames: (chunkInfo) => {
          // Generate meaningful chunk names
          if (chunkInfo.name === 'vendor') {
            return `vendor.[hash].js`;
          }
          return `${chunkInfo.name}.[hash].js`;
        }
      },
      // Optimize chunks
      optimizeDeps: {
        include: ['react', 'react-dom', 'react-router-dom', '@tanstack/react-query', 'axios', 'lucide-react']
      }
    },
    // Asset optimization
    assetsInlineLimit: 4096, // Inline small assets as base64
    cssCodeSplit: true,
    // Generate manifest for PWA
    manifest: {
      name: 'QuizMe',
      short_name: 'QuizMe',
      description: 'Interactive quiz application',
      theme_color: '#3b82f6',
      background_color: '#ffffff',
      display: 'standalone',
      start_url: '/',
      icons: [
        {
          src: '/icon-192x192.png',
          sizes: '192x192',
          type: 'image/png'
        },
        {
          src: '/icon-512x512.png',
          sizes: '512x512',
          type: 'image/png'
        }
      ]
    }
  },
  server: {
    port: 3000,
    host: true,
    // Proxy configuration for development
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        secure: false
      },
      '/mcq': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        secure: false
      }
    }
  },
  // Resolve paths
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@components': resolve(__dirname, 'src/components'),
      '@pages': resolve(__dirname, 'src/pages'),
      '@utils': resolve(__dirname, 'src/utils'),
      '@hooks': resolve(__dirname, 'src/hooks')
    }
  },
  // Define global constants
  define: {
    __APP_VERSION__: JSON.stringify(process.env.npm_package_version),
    __BUILD_TIME__: JSON.stringify(new Date().toISOString()),
    __ENV__: JSON.stringify(process.env.NODE_ENV || 'production')
  },
  // CSS optimization
  css: {
    devSourcemap: true,
    preprocessorOptions: {
      less: {
        javascriptEnabled: true
      }
    }
  },
  // Development optimizations
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-router-dom', '@tanstack/react-query', 'axios', 'lucide-react']
  }
})
