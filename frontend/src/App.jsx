import { Routes, Route, Navigate } from 'react-router-dom'
import LogInteractionPage from './pages/LogInteractionPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/log" replace />} />
      <Route path="/log" element={<LogInteractionPage />} />
    </Routes>
  )
}
