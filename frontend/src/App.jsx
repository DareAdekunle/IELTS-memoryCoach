import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import AppShell from './components/AppShell'

import Login from './pages/Login'
import Register from './pages/Register'
import AuthCallback from './pages/AuthCallback'
import Onboarding from './pages/Onboarding'
import Dashboard from './pages/Dashboard'
import WritingCoach from './pages/WritingCoach'
import ReadingCoach from './pages/ReadingCoach'
import SpeakingCoach from './pages/SpeakingCoach'
import ProgressDashboard from './pages/ProgressDashboard'
import MemoryDashboard from './pages/MemoryDashboard'
import ListeningCoach from './pages/ListeningCoach'
import ChatCoach from './pages/ChatCoach'

function ProtectedShell({ children }) {
  return (
    <ProtectedRoute>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/auth/callback" element={<AuthCallback />} />
          <Route path="/onboarding" element={
            <ProtectedRoute><Onboarding /></ProtectedRoute>
          } />

          {/* Protected with shell */}
          <Route path="/dashboard" element={
            <ProtectedShell><Dashboard /></ProtectedShell>
          } />
          <Route path="/writing" element={
            <ProtectedShell><WritingCoach /></ProtectedShell>
          } />
          <Route path="/reading" element={
            <ProtectedShell><ReadingCoach /></ProtectedShell>
          } />
          <Route path="/progress" element={
            <ProtectedShell><ProgressDashboard /></ProtectedShell>
          } />
          <Route path="/memory" element={
            <ProtectedShell><MemoryDashboard /></ProtectedShell>
          } />
          <Route path="/speaking" element={
            <ProtectedShell><SpeakingCoach /></ProtectedShell>
          } />
          <Route path="/listening" element={
            <ProtectedShell><ListeningCoach /></ProtectedShell>
          } />
          <Route path="/chat" element={
            <ProtectedShell><ChatCoach /></ProtectedShell>
          } />

          {/* Catch-all route */} 
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}