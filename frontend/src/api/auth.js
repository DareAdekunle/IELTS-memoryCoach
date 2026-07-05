import client from './client'

export const register = (data) => client.post('/auth/register', data)
export const login = (data) => client.post('/auth/login', data)
export const getMe = () => client.get('/auth/me')
export const logout = () => client.post('/auth/logout')

export const googleLogin = () => {
  window.location.href = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/auth/google`
}