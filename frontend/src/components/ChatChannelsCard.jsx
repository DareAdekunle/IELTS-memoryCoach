import { useState, useEffect } from 'react'
import { Check, Copy, ExternalLink, MessageCircle, Send, Unlink } from 'lucide-react'
import { getChannelStatus, createLinkCode, disconnectChannel } from '../api/channels'

const CHANNELS = [
  { id: 'telegram', name: 'Telegram', icon: Send, sendHint: 'Send this code to the BandUp bot on Telegram:' },
  { id: 'whatsapp', name: 'WhatsApp', icon: MessageCircle, sendHint: 'Send this message to BandUp on WhatsApp:' },
]

function secondsLeft(expiresAt) {
  return Math.max(0, Math.round((new Date(expiresAt) - Date.now()) / 1000))
}

function formatCountdown(seconds) {
  const m = Math.floor(seconds / 60)
  const s = String(seconds % 60).padStart(2, '0')
  return m + ':' + s
}

export default function ChatChannelsCard() {
  const [status, setStatus]   = useState({ telegram: false, whatsapp: false })
  const [pending, setPending] = useState({})   // channel → {code, expires_at, deep_link}
  const [error, setError]     = useState('')
  const [copied, setCopied]   = useState(null)
  const [, setTick]           = useState(0)

  useEffect(() => {
    getChannelStatus().then(setStatus).catch(() => {})
  }, [])

  const hasPending = Object.keys(pending).length > 0

  // While a code is showing: refresh the countdown and watch for the bot linking it.
  useEffect(() => {
    if (!hasPending) return undefined
    const timer = setInterval(async () => {
      setTick(t => t + 1)
      try {
        const next = await getChannelStatus()
        setStatus(next)
        setPending(p => Object.fromEntries(Object.entries(p).filter(([ch]) => !next[ch])))
      } catch { /* keep polling */ }
    }, 3000)
    return () => clearInterval(timer)
  }, [hasPending])

  const handleConnect = async (channel) => {
    setError('')
    try {
      const data = await createLinkCode(channel)
      setPending(p => ({ ...p, [channel]: data }))
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not create a link code.')
    }
  }

  const handleDisconnect = async (channel, name) => {
    if (!window.confirm('Disconnect ' + name + '? The coach will stop replying there.')) return
    try {
      setStatus(await disconnectChannel(channel))
    } catch {
      setError('Could not disconnect ' + name + '.')
    }
  }

  const handleCopy = async (channel, text) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(channel)
      setTimeout(() => setCopied(null), 1500)
    } catch { /* clipboard unavailable */ }
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-6 mt-4">
      <h2 className="font-semibold text-gray-900 mb-1">Chat with your coach</h2>
      <p className="text-sm text-gray-500 mb-4">
        Ask how you're doing or reschedule study sessions from Telegram or WhatsApp.
      </p>
      {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

      <div className="divide-y divide-gray-100">
        {CHANNELS.map(({ id, name, icon: Icon, sendHint }) => {
          const linked    = status[id]
          const code      = pending[id]
          const remaining = code ? secondsLeft(code.expires_at) : 0
          const expired   = code && remaining === 0
          const message   = id === 'whatsapp' && code ? 'LINK ' + code.code : (code ? code.code : '')
          return (
            <div key={id} className="py-4 first:pt-0 last:pb-0">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <Icon className="w-4 h-4 text-gray-500" />
                  <span className="text-sm font-medium text-gray-900">{name}</span>
                  {linked && (
                    <span className="flex items-center gap-1 text-xs font-medium text-green-700 bg-green-50 rounded-full px-2 py-0.5">
                      <Check className="w-3 h-3" /> Connected
                    </span>
                  )}
                </div>
                {linked ? (
                  <button
                    onClick={() => handleDisconnect(id, name)}
                    className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-red-500"
                  >
                    <Unlink className="w-4 h-4" /> Disconnect
                  </button>
                ) : (
                  <button
                    onClick={() => handleConnect(id)}
                    className="text-sm font-medium text-brand-600 hover:text-brand-700"
                  >
                    {code ? 'New code' : 'Connect ' + name}
                  </button>
                )}
              </div>

              {code && !linked && (
                <div className="mt-3 rounded-xl bg-gray-50 border border-gray-200 p-4">
                  {expired ? (
                    <p className="text-sm text-gray-500">This code has expired. Get a new one to connect.</p>
                  ) : (
                    <>
                      <p className="text-sm text-gray-600 mb-2">{sendHint}</p>
                      <div className="flex items-center gap-3">
                        <code className="text-lg font-semibold tracking-widest text-gray-900">{message}</code>
                        <button
                          onClick={() => handleCopy(id, message)}
                          className="text-gray-400 hover:text-gray-600"
                          aria-label={'Copy ' + name + ' code'}
                        >
                          {copied === id ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
                        </button>
                      </div>
                      <div className="flex items-center justify-between mt-3 text-xs text-gray-500">
                        <span>Expires in {formatCountdown(remaining)} · waiting for {name}…</span>
                        {code.deep_link && (
                          <a
                            href={code.deep_link}
                            target="_blank"
                            rel="noreferrer"
                            className="flex items-center gap-1 font-medium text-brand-600 hover:text-brand-700"
                          >
                            Open {name} <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
