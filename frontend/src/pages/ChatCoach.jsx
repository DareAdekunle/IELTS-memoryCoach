import { useState, useEffect, useRef } from 'react'
import { startChat, continueChat } from '../api/chat'
import { useAuth } from '../context/AuthContext'
import { Loader2, Send, MessageSquare, Zap, PenLine } from 'lucide-react'
import { Link } from 'react-router-dom'

const STATE_LABELS = {
  introduction: { label: 'Getting started', color: 'text-blue-400' },
  explaining: { label: 'Learning the skill', color: 'text-purple-400' },
  drilling: { label: 'Practising with drills', color: 'text-yellow-400' },
  bridge_to_practice: { label: 'Ready for a full essay', color: 'text-green-400' },
}

export default function ChatCoach() {
  const { user } = useAuth()
  const [messages, setMessages] = useState([])
  const [systemPrompt, setSystemPrompt] = useState('')
  const [state, setState] = useState(null)
  const [hasHistory, setHasHistory] = useState(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    initSession()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const initSession = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await startChat()
      const data = res.data
      setMessages([{ role: 'assistant', content: data.message }])
      setState(data.state)
      setHasHistory(data.has_history)
      setSystemPrompt(data.system_prompt || '')
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not start chat session.')
    } finally {
      setLoading(false)
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }

  const handleSend = async () => {
    const text = input.trim()
    if (!text || sending) return

    const userMessage = { role: 'user', content: text }
    const newMessages = [...messages, userMessage]
    setMessages(newMessages)
    setInput('')
    setSending(true)
    setError('')

    try {
      if (!hasHistory) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content:
              "I'll be able to help much more once you've tried the Writing Coach! Head over there to submit your first essay, then come back and chat with me 😊",
          },
        ])
        setSending(false)
        return
      }

      const historyForCall = newMessages.slice(0, -1)

      const res = await continueChat({
        system_prompt: systemPrompt,
        history: historyForCall,
        message: text,
      })

      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: res.data.message },
      ])
      setState(res.data.state)
    } catch (err) {
      setError(err.response?.data?.detail || 'Something went wrong. Please try again.')
    } finally {
      setSending(false)
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const stateInfo = state ? STATE_LABELS[state] : null
  const firstName = user?.full_name?.split(' ')[0] || user?.username || 'there'

  return (
    <div className="flex flex-col h-[calc(100vh-0px)] max-h-screen">

      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-gray-800
                      bg-gray-950">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-500/20 flex items-center
                            justify-center">
              <MessageSquare className="w-5 h-5 text-brand-400" />
            </div>
            <div>
              <h1 className="text-white font-semibold">Chat Coach</h1>
              <p className="text-gray-500 text-xs">
                Your personal IELTS writing tutor
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {stateInfo && (
              <span className={'text-xs font-medium ' + stateInfo.color}>
                {stateInfo.label}
              </span>
            )}
            <button
              onClick={() => {
                setMessages([])
                setSystemPrompt('')
                setState(null)
                setHasHistory(null)
                initSession()
              }}
              className="text-xs text-gray-500 hover:text-gray-300
                         transition-colors px-3 py-1.5 bg-gray-800
                         hover:bg-gray-700 rounded-lg"
            >
              New conversation
            </button>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="max-w-3xl mx-auto space-y-4">

          {loading && (
            <div className="flex items-center gap-3 text-gray-400">
              <Loader2 className="w-5 h-5 animate-spin text-brand-500" />
              <span className="text-sm">Your coach is reviewing your progress...</span>
            </div>
          )}

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={
                'flex gap-3 ' + (msg.role === 'user' ? 'justify-end' : 'justify-start')
              }
            >
              {msg.role === 'assistant' && (
                <div className="w-8 h-8 rounded-full bg-brand-500/20 flex items-center
                                justify-center flex-shrink-0 mt-1">
                  <Zap className="w-4 h-4 text-brand-400" />
                </div>
              )}

              <div
                className={
                  'max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ' +
                  (msg.role === 'user'
                    ? 'bg-brand-500 text-white rounded-br-sm'
                    : 'bg-gray-900 border border-gray-800 text-gray-300 rounded-bl-sm')
                }
              >
                {msg.content.split('\n').map((line, j) => (
                  <span key={j}>
                    {line}
                    {j < msg.content.split('\n').length - 1 && <br />}
                  </span>
                ))}
              </div>

              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center
                                justify-center flex-shrink-0 mt-1 text-sm font-bold
                                text-gray-300">
                  {firstName[0].toUpperCase()}
                </div>
              )}
            </div>
          ))}

          {sending && (
            <div className="flex gap-3 justify-start">
              <div className="w-8 h-8 rounded-full bg-brand-500/20 flex items-center
                              justify-center flex-shrink-0">
                <Zap className="w-4 h-4 text-brand-400" />
              </div>
              <div className="bg-gray-900 border border-gray-800 rounded-2xl
                              rounded-bl-sm px-4 py-3">
                <div className="flex gap-1">
                  <div className="w-2 h-2 rounded-full bg-gray-600 animate-bounce"
                       style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 rounded-full bg-gray-600 animate-bounce"
                       style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 rounded-full bg-gray-600 animate-bounce"
                       style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}

          {/* Bridge to practice button */}
          {state === 'bridge_to_practice' && !sending && (
            <div className="flex justify-center py-2">
              <Link
                to="/writing"
                className="flex items-center gap-2 px-6 py-3 bg-brand-500
                           hover:bg-brand-600 text-white font-semibold rounded-xl
                           transition-colors"
              >
                <PenLine className="w-4 h-4" />
                Go to Writing Coach to practise →
              </Link>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="flex-shrink-0 px-6 py-4 border-t border-gray-800 bg-gray-950">
        <div className="max-w-3xl mx-auto">
          <div className="flex gap-3 items-end">
            <div className="flex-1 bg-gray-900 border border-gray-800
                            rounded-2xl px-4 py-3 focus-within:border-brand-500
                            transition-colors">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  loading
                    ? 'Waiting for your coach...'
                    : 'Type your message... (Enter to send)'
                }
                disabled={loading || sending}
                rows={1}
                className="w-full bg-transparent text-white placeholder-gray-600
                           text-sm resize-none focus:outline-none
                           disabled:opacity-50"
                style={{ maxHeight: '120px' }}
                onInput={(e) => {
                  e.target.style.height = 'auto'
                  e.target.style.height = e.target.scrollHeight + 'px'
                }}
              />
            </div>
            <button
              onClick={handleSend}
              disabled={!input.trim() || loading || sending}
              className="w-12 h-12 flex items-center justify-center bg-brand-500
                         hover:bg-brand-600 disabled:opacity-40
                         disabled:cursor-not-allowed text-white rounded-2xl
                         transition-colors flex-shrink-0"
            >
              {sending ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
          <p className="text-gray-600 text-xs mt-2 text-center">
            Your coach focuses on your weakest writing skill · Press Enter to send
          </p>
        </div>
      </div>
    </div>
  )
}
