import client from './client'

export const register = (data) => client.post('/auth/register', data)
export const login = (data) => client.post('/auth/login', data)
export const getMe = () => client.get('/auth/me')
export const logout = () => client.post('/auth/logout')

export const googleLogin = () => {
  // Use same base URL as axios client
  const API_BASE = import.meta.env.VITE_API_URL || '/api'
  window.location.href = `${API_BASE}/auth/google`
}
