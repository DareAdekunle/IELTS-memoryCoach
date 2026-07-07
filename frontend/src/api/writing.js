import client from './client'

export const getPrompt = () => client.get('/writing/prompt')
export const getWritingMemories = () => client.get('/writing/memories')
export const submitEssay = (data) => client.post('/writing/submit', data)
export const getWritingAttempts = () => client.get('/writing/attempts')

/**
 * Streaming essay submission via Server-Sent Events.
 * Calls onToken for each streamed token (fast TTFT ~1-2s).
 * Calls onComplete with full parsed result when done.
 * Calls onError on any failure.
 */
export const submitEssayStream = async (data, onToken, onComplete, onError) => {
  const token = localStorage.getItem('token')
  const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

  try {
    const response = await fetch(`${API_BASE}/writing/submit/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(data)
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      onError(err.detail || 'Submission failed')
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')

      // Keep incomplete last line in buffer
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const payload = line.slice(6).trim()
        if (!payload) continue

        try {
          const parsed = JSON.parse(payload)
          if (parsed.token !== undefined) onToken(parsed.token)
          if (parsed.done) onComplete(parsed.result)
          if (parsed.error) onError(parsed.error)
        } catch {
          // Ignore malformed SSE chunks
        }
      }
    }
  } catch (err) {
    onError(err.message || 'Connection failed')
  }
}
