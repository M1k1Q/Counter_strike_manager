import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import EventAtmosphere from './components/EventAtmosphere.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <EventAtmosphere />
    <App />
  </StrictMode>,
)
