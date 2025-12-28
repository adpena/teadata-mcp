import React from 'react'
import ReactDOM from 'react-dom/client'
import { AppsSDKUIProvider } from '@openai/apps-sdk-ui/components/AppsSDKUIProvider'
import App from './App'
import 'leaflet/dist/leaflet.css'
import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'
import 'maplibre-gl/dist/maplibre-gl.css'
import './index.css'

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <AppsSDKUIProvider linkComponent="a">
      <App />
    </AppsSDKUIProvider>
  </React.StrictMode>,
)
