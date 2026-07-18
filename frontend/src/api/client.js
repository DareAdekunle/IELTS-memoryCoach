import axios from 'axios'

// In development: React (5173) and FastAPI (8000) run separately
// In production: Nginx serves both — React on / and FastAPI on /api/
const API_BASE = import.meta.env.VITE_API_URL || '/api'

const client = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  // AI turns can stack multiple model calls (tutor reply + tools).
  // 150s keeps slow turns alive but surfaces genuinely hung requests.
  timeout: 150000
})

// Attach JWT token to every request automatically
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 401 → clear token and redirect to login
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default client
