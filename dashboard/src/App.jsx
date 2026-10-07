import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar.jsx'
import Dashboard from './pages/Dashboard.jsx'
import LiveMonitor from './pages/LiveMonitor.jsx'
import LiveCamera from './pages/LiveCamera.jsx'
import Violations from './pages/Violations.jsx'
import Snapshots from './pages/Snapshots.jsx'
import Analytics from './pages/Analytics.jsx'

export default function App() {
  return (
    <div className="min-h-screen">
      <Sidebar systemOk={true} />
      <main className="ml-0 lg:ml-64">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/live" element={<LiveMonitor />} />
            <Route path="/live-camera" element={<LiveCamera />} />
            <Route path="/violations" element={<Violations />} />
            <Route path="/snapshots" element={<Snapshots />} />
            <Route path="/analytics" element={<Analytics />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}
