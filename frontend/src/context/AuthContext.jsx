import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import api from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => JSON.parse(localStorage.getItem('user') || 'null'))
  const [loading, setLoading] = useState(Boolean(localStorage.getItem('accessToken')))

  const refreshProfile = useCallback(async () => {
    const { data } = await api.get('/auth/profile/')
    setUser(data); localStorage.setItem('user', JSON.stringify(data)); return data
  }, [])

  useEffect(() => {
    if (localStorage.getItem('accessToken')) refreshProfile().catch(() => setUser(null)).finally(() => setLoading(false))
  }, [refreshProfile])

  const login = async (credentials) => {
    const { data } = await api.post('/auth/login/', credentials)
    localStorage.setItem('accessToken', data.access); localStorage.setItem('refreshToken', data.refresh); localStorage.setItem('user', JSON.stringify(data.user)); setUser(data.user)
  }
  const logout = () => { localStorage.removeItem('accessToken'); localStorage.removeItem('refreshToken'); localStorage.removeItem('user'); setUser(null) }
  const value = useMemo(() => ({ user, setUser, login, logout, loading, refreshProfile, isAdmin: user?.role === 'ASSISTANT_PRINCIPAL' }), [user, loading, refreshProfile])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)

