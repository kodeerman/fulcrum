import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { md3 } from 'vuetify/blueprints'

import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import './assets/styles/global.css'
const vuetify = createVuetify({
  components,
  directives,
  blueprint: md3,
  theme: {
    defaultTheme: 'light',
    themes: {
      light: {
        colors: {
          primary: '#003466', // We can change this to something else
          background: '#f8f8f8',
          surface: '#ffffff',
        },
      },
      dark: {
        dark: true,
        colors: {
          primary: '#9dceff',
          background: '#111c2b',
          surface: '#1b2a3c',
          'surface-variant': '#30435a',
          'on-surface-variant': '#e6edf5',
          'on-background': '#e6edf5',
          'on-surface': '#e6edf5',
        },
      },
    },
  },
})

const app = createApp(App)

app.use(createPinia())
// Access the backend URL and port from Vite's injected environment variables "config.json"
const backendUrl = `${import.meta.env.VITE_BACKEND_URL}:${import.meta.env.VITE_BACKEND_PORT}`

// Make the backend URL globally available
app.config.globalProperties.$backendUrl = backendUrl

app.use(router)
app.use(vuetify)
app.mount('#app')
