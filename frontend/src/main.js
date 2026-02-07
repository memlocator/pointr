import { mount } from 'svelte'
import './app.css'
import 'maplibre-gl/dist/maplibre-gl.css'
import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css'
import App from './App.svelte'
import { APP_TITLE } from './config.js'

// Set document title from config
document.title = APP_TITLE

const app = mount(App, {
  target: document.getElementById('app'),
})

export default app
