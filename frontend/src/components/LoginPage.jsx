import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from './ui/Card'
import './LoginPage.css'

function LoginPage({ onLoginSuccess }) {
  const [isRegister, setIsRegister] = useState(false)

  // Form inputs
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  // Feedback states
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [successMsg, setSuccessMsg] = useState(null)

  // Password strength checks
  const hasMinLength = password.length >= 8
  const hasUpper = /[A-Z]/.test(password)
  const hasLower = /[a-z]/.test(password)
  const hasNumber = /\d/.test(password)
  const isPasswordValid = hasMinLength && hasUpper && hasLower && hasNumber

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setSuccessMsg(null)

    if (isRegister) {
      if (!isPasswordValid) {
        setError('Password does not meet all security requirements.')
        return
      }
    }

    setLoading(true)

    try {
      const endpoint = isRegister ? '/api/auth/register' : '/api/auth/login'
      const payload = isRegister
        ? { username, email, password }
        : { username_or_email: username, password }

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      const contentType = res.headers.get('content-type')
      let data = {}
      if (contentType && contentType.includes('application/json')) {
        data = await res.json()
      } else {
        const text = await res.text()
        data = { detail: text || `Server error (${res.status})` }
      }

      if (!res.ok) {
        throw new Error(data.detail || 'Authentication failed. Please check your credentials.')
      }

      setSuccessMsg(isRegister ? 'Account created successfully! Logging you in...' : 'Login successful!')

      // Save auth token in localStorage & update state
      if (data.access_token) {
        localStorage.setItem('cs_manager_token', data.access_token)
        localStorage.setItem('cs_manager_user', JSON.stringify(data.user))
      }

      setTimeout(() => {
        onLoginSuccess(data)
      }, 500)
    } catch (err) {
      console.error('Auth error:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // Quick fill demo user for easy testing
  const handleFillDemo = (type) => {
    setError(null)
    setSuccessMsg(null)
    if (type === 'admin') {
      setIsRegister(false)
      setUsername('pro_manager')
      setPassword('Manager123!')
    } else {
      setIsRegister(true)
      setUsername('test_user_' + Math.floor(Math.random() * 1000))
      setEmail(`player${Math.floor(Math.random() * 1000)}@esports.com`)
      setPassword('SecurePass123!')
    }
  }

  return (
    <div className="auth-wrapper fade-in">
      <Card className="auth-card-shadcn">
        <CardHeader className="auth-header">
          <div className="auth-badge">
            <span className="auth-badge-icon">⚡</span> CS MANAGER AUTH
          </div>
          <CardTitle>
            {isRegister ? 'Create Your Account' : 'Manager Authentication'}
          </CardTitle>
          <CardDescription className="auth-subtitle">
            {isRegister
              ? 'Join the premier esports management platform safely.'
              : 'Sign in to access your roster, tactics, and transfer budget.'}
          </CardDescription>
        </CardHeader>

        <CardContent>
          {/* Auth Mode Toggle */}
          <div className="auth-tabs">
            <button
              type="button"
              className={`auth-tab ${!isRegister ? 'active' : ''}`}
              onClick={() => {
                setIsRegister(false)
                setError(null)
              }}
            >
              Sign In
            </button>
            <button
              type="button"
              className={`auth-tab ${isRegister ? 'active' : ''}`}
              onClick={() => {
                setIsRegister(true)
                setError(null)
              }}
            >
              Register Account
            </button>
          </div>

          {/* Error / Success Banners */}
          {error && (
            <div className="auth-alert error">
              <span className="alert-icon">⚠️</span>
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="auth-alert success">
              <span className="alert-icon">✅</span>
              <span>{successMsg}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="auth-form">
            <div className="form-group">
              <label htmlFor="username">
                {isRegister ? 'Username' : 'Username or Email'}
              </label>
              <div className="input-field">
                <span className="input-icon">👤</span>
                <input
                  id="username"
                  type="text"
                  placeholder={isRegister ? 'e.g. s1mple_fan' : 'Enter username or email'}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  autoFocus
                />
              </div>
            </div>

            {isRegister && (
              <div className="form-group fade-in">
                <label htmlFor="email">Email Address</label>
                <div className="input-field">
                  <span className="input-icon"></span>
                  <input
                    id="email"
                    type="email"
                    placeholder="manager@esports.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
              </div>
            )}

            <div className="form-group">
              <label htmlFor="password">Password</label>
              <div className="input-field">
                <span className="input-icon"></span>
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  className={`toggle-password ${showPassword ? 'status-valid' : 'status-invalid'}`}
                  onClick={() => setShowPassword(!showPassword)}
                  title={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? '✓' : '✘'}
                </button>
              </div>
            </div>

            {/* Password Security Rules for Register */}
            {isRegister && password.length > 0 && (
              <div className="password-rules fade-in">
                <div className="rules-title">Password Security Requirements:</div>
                <div className={`rule-item ${hasMinLength ? 'met' : ''}`}>
                  {hasMinLength ? '✓' : '○'} At least 8 characters
                </div>
                <div className={`rule-item ${hasUpper ? 'met' : ''}`}>
                  {hasUpper ? '✓' : '○'} At least 1 uppercase letter (A-Z)
                </div>
                <div className={`rule-item ${hasLower ? 'met' : ''}`}>
                  {hasLower ? '✓' : '○'} At least 1 lowercase letter (a-z)
                </div>
                <div className={`rule-item ${hasNumber ? 'met' : ''}`}>
                  {hasNumber ? '✓' : '○'} At least 1 number (0-9)
                </div>
              </div>
            )}

            <button
              type="submit"
              className="btn-primary auth-submit-btn"
              disabled={loading || (isRegister && !isPasswordValid)}
            >
              {loading ? (
                <span className="spinner-text">
                  <span className="spinner"></span> Authenticating...
                </span>
              ) : isRegister ? (
                'Create Secure Account'
              ) : (
                'Sign In to Dashboard'
              )}
            </button>
          </form>
        </CardContent>

        <CardFooter className="auth-demo-footer-shadcn">
          <span className="demo-label">Testing Shortcuts:</span>
          <div className="demo-buttons">
            <button
              type="button"
              className="btn-demo"
              onClick={() => handleFillDemo('new')}
            >
              ⚡ Fill Random New User
            </button>
          </div>
        </CardFooter>
      </Card>
    </div>
  )
}

export default LoginPage
