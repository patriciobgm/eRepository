import { CircularProgress, Box } from '@mui/material'
import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import { useAuth } from './context/AuthContext'
import ActivityPage from './pages/ActivityPage'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'
import ProfilePage from './pages/ProfilePage'
import RepositoriesPage from './pages/RepositoriesPage'
import RegisterPage from './pages/RegisterPage'
import StaffPage from './pages/StaffPage'

function Protected({ children, admin = false }) {
  const { user, loading, isAdmin } = useAuth()
  if (loading) return <Box minHeight="100vh" display="grid" sx={{ placeItems: 'center' }}><CircularProgress /></Box>
  if (!user) return <Navigate to="/login" replace />
  if (admin && !isAdmin) return <Navigate to="/" replace />
  return children
}

export default function App() {
  const { user } = useAuth()
  return <Routes>
    <Route path="/login" element={user ? <Navigate to="/" replace /> : <LoginPage />} />
    <Route path="/register" element={user ? <Navigate to="/" replace /> : <RegisterPage />} />
    <Route element={<Protected><AppLayout /></Protected>}>
      <Route index element={<DashboardPage />} />
      <Route path="repositories" element={<RepositoriesPage />} />
      <Route path="activity" element={<ActivityPage />} />
      <Route path="profile" element={<ProfilePage />} />
      <Route path="staff" element={<Protected admin><StaffPage /></Protected>} />
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
}
