import axios from 'axios'

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

const api = axios.create({ baseURL: API_URL })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use((response) => response, async (error) => {
  const original = error.config
  if (error.response?.status === 401 && !original?._retry && localStorage.getItem('refreshToken')) {
    original._retry = true
    try {
      const { data } = await axios.post(`${API_URL}/auth/token/refresh/`, { refresh: localStorage.getItem('refreshToken') })
      localStorage.setItem('accessToken', data.access)
      if (data.refresh) localStorage.setItem('refreshToken', data.refresh)
      original.headers.Authorization = `Bearer ${data.access}`
      return api(original)
    } catch {
      localStorage.removeItem('accessToken'); localStorage.removeItem('refreshToken'); localStorage.removeItem('user')
      window.location.assign('/login')
    }
  }
  return Promise.reject(error)
})

export const errorMessage = (error) => {
  const data = error.response?.data
  if (!data) return 'Something went wrong. Please try again.'
  if (typeof data === 'string') return data
  if (data.detail) return Array.isArray(data.detail) ? data.detail.join(' ') : data.detail
  const value = Object.values(data)[0]
  return Array.isArray(value) ? value.join(' ') : typeof value === 'object' ? Object.values(value).flat().join(' ') : String(value)
}

export default api

