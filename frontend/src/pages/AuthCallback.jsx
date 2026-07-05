import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getMe } from '../api/auth'

export default function AuthCallback() {
  const [searchParams] = useSearchParams()
  const { loginUser } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    const token = searchParams.get('token')
    const error = searchParams.get('error')

    if (error || !token) {
      navigate('/login?error=oauth_failed')
      return
    }

    // Store token then fetch user details
    localStorage.setItem('token', token)

    getMe()
      .then(res => {
        loginUser(token, res.data)
        // If no learner profile yet go to onboarding, otherwise dashboard
        if (!res.data.learner_id) {
          navigate('/onboarding')
        } else {
          navigate('/dashboard')
        }
      })
      .catch(() => {
        localStorage.removeItem('token')
        navigate('/login?error=oauth_failed')
      })
  }, [])

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="w-12 h-12 border-4 border-brand-500 border-t-transparent
                        rounded-full animate-spin mx-auto mb-4" />
        <p className="text-gray-400">Completing sign in...</p>
      </div>
    </div>
  )
}