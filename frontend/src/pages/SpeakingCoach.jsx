import { useState, useEffect, useRef, useCallback } from 'react'
import {
  getRandomSpeakingPrompt,
  getSpeakingMemories,
  transcribeAudio,
  evaluateSpeaking,
  generateTTS,
} from '../api/speaking'
import {
  Mic, MicOff, Upload, CheckCircle,
  Loader2, ChevronRight, Volume2, Brain, RefreshCw,
} from 'lucide-react'

export default function SpeakingCoach() {
  const [phase, setPhase]               = useState('loading')  // loading | session | results
  const [prompt, setPrompt]             = useState(null)
  const [memories, setMemories]         = useState([])
  const [currentPart, setCurrentPart]   = useState('part1')
  const [part1Responses, setPart1Responses] = useState({})
  const [part2Response, setPart2Response]   = useState('')
  const [part3Responses, setPart3Responses] = useState({})
  const [results, setResults]           = useState(null)
  const [ttsUrl, setTtsUrl]             = useState(null)
  const [fetching, setFetching]         = useState(false)
  const [submitting, setSubmitting]     = useState(false)
  const [transcribing, setTranscribing] = useState({})
  const [error, setError]               = useState('')
  const [recording, setRecording]       = useState(null)
  const mediaRecorderRef = useRef(null)
  const chunksRef        = useRef([])

  const loadPrompt = useCallback(async () => {
    setFetching(true)
    setError('')
    setPart1Responses({})
    setPart2Response('')
    setPart3Responses({})
    setResults(null)
    setTtsUrl(null)
    setCurrentPart('part1')

    try {
      const [promptRes, memRes] = await Promise.all([
        getRandomSpeakingPrompt(),   // backend returns adaptive unseen prompt
        getSpeakingMemories()
      ])
      setPrompt(promptRes.data.prompt)
      setMemories(memRes.data.memories || [])
      setPhase('session')
    } catch {
      setError('Could not load speaking prompt. Please refresh.')
    } finally {
      setFetching(false)
    }
  }, [])

  useEffect(() => { loadPrompt() }, [loadPrompt])

  const startRecording = async (key) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      chunksRef.current = []
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mr.ondataavailable = (e) => chunksRef.current.push(e.data)
      mr.onstop = () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        handleAudioBlob(blob, key)
      }
      mr.start()
      mediaRecorderRef.current = mr
      setRecording(key)
    } catch {
      setError('Could not access microphone. Please use file upload instead.')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop()
      mediaRecorderRef.current = null
    }
    setRecording(null)
  }

  const handleAudioBlob = async (blob, key) => {
    setTranscribing(prev => ({ ...prev, [key]: true }))
    try {
      const res = await transcribeAudio(blob, 'recording.webm')
      const text = res.data.text
      if (key.startsWith('p1_')) {
        const idx = key.replace('p1_', '')
        setPart1Responses(prev => ({ ...prev, [idx]: text }))
      } else if (key === 'p2') {
        setPart2Response(text)
      } else if (key.startsWith('p3_')) {
        const idx = key.replace('p3_', '')
        setPart3Responses(prev => ({ ...prev, [idx]: text }))
      }
    } catch (err) {
      setError('Transcription failed: ' + (err.response?.data?.detail || 'Please try again.'))
    } finally {
      setTranscribing(prev => ({ ...prev, [key]: false }))
    }
  }

  const handleFileUpload = (e, key) => {
    const file = e.target.files[0]
    if (!file) return
    handleAudioBlob(file, key)
    e.target.value = ''
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    setError('')
    try {
      const res = await evaluateSpeaking({
        prompt_set_id: prompt.prompt_set_id,
        part1_responses: part1Responses,
        part2_response: part2Response,
        part3_responses: part3Responses,
      })
      setResults(res.data)
      setPhase('results')
      try {
        const audioUrl = await generateTTS(res.data.feedback_text)
        setTtsUrl(audioUrl)
      } catch { /* TTS optional */ }
    } catch (err) {
      setError(err.response?.data?.detail || 'Evaluation failed.')
    } finally {
      setSubmitting(false)
    }
  }

  // Completion checks
  const p1Done = prompt ? Object.keys(part1Responses).length >= prompt.part1.questions.length : false
  const p2Done = part2Response.length > 0
  const p3Done = prompt ? Object.keys(part3Responses).length >= prompt.part3.questions.length : false

  function AudioInput({ questionKey, existingText, onClear }) {
    const isTranscribing = transcribing[questionKey]
    const isRecording    = recording === questionKey

    if (isTranscribing) return (
      <div className="flex items-center gap-2 text-gray-400 text-sm bg-gray-800 rounded-xl px-4 py-3">
        <Loader2 className="w-4 h-4 animate-spin" />Transcribing your answer...
      </div>
    )

    if (existingText) return (
      <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-3">
        <div className="flex items-start gap-2 mb-2">
          <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0 mt-0.5" />
          <p className="text-gray-300 text-sm italic">"{existingText}"</p>
        </div>
        <button onClick={onClear} className="text-gray-500 text-xs hover:text-gray-300 transition-colors">Redo</button>
      </div>
    )

    return (
      <div className="flex items-center gap-3 bg-gray-800 rounded-xl px-4 py-3">
        <button
          onClick={() => isRecording ? stopRecording() : startRecording(questionKey)}
          className={isRecording
            ? 'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-red-500 text-white animate-pulse'
            : 'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-gray-700 text-gray-300 hover:bg-gray-600'
          }
        >
          {isRecording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          {isRecording ? 'Stop' : 'Record'}
        </button>
        <span className="text-gray-600 text-sm">or</span>
        <label className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-gray-700 text-gray-300 hover:bg-gray-600 cursor-pointer">
          <Upload className="w-4 h-4" />Upload
          <input type="file" accept="audio/*" className="hidden" onChange={e => handleFileUpload(e, questionKey)} />
        </label>
      </div>
    )
  }

  if (fetching && phase === 'loading') return (
    <div className="flex items-center justify-center h-96">
      <div className="text-center">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin mx-auto mb-3" />
        <p className="text-gray-400">Loading your speaking session...</p>
      </div>
    </div>
  )

  return (
    <div className="p-6 max-w-4xl mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Mic className="w-6 h-6 text-green-400" />
            Speaking Coach
          </h1>
          <p className="text-gray-400 mt-1">
            {prompt ? `Topic: ${prompt.topic}` : 'Topic adapted to your current band level'}
          </p>
        </div>
        {phase !== 'loading' && (
          <button
            onClick={loadPrompt}
            disabled={fetching}
            className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-300 rounded-xl text-sm transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${fetching ? 'animate-spin' : ''}`} />
            New topic
          </button>
        )}
      </div>

      {/* Memory panel */}
      {memories.length > 0 && phase === 'session' && (
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 mb-6">
          <div className="flex items-center gap-2 mb-2">
            <Brain className="w-4 h-4 text-green-400" />
            <span className="text-sm font-medium text-gray-300">What your coach remembers</span>
          </div>
          {memories.map((mem, i) => (
            <p key={i} className="text-gray-400 text-sm">
              {mem.memory_type === 'weakness' ? '⚠️' : '✅'} <span className="text-gray-300">{mem.skill}:</span> {mem.memory_text}
            </p>
          ))}
        </div>
      )}

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-6">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {/* SESSION phase */}
      {phase === 'session' && prompt && (
        <div className="space-y-6">
          {/* Part progress */}
          <div className="flex items-center gap-2">
            {['part1', 'part2', 'part3'].map((partKey, i) => {
              const isActive = currentPart === partKey
              const isDone = (i === 0 && p1Done) || (i === 1 && p2Done) || (i === 2 && p3Done)
              return (
                <div key={partKey} className="flex items-center gap-2">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                    isDone ? 'bg-green-500 text-white' : isActive ? 'bg-brand-500 text-white' : 'bg-gray-800 text-gray-500'
                  }`}>{i + 1}</div>
                  {i < 2 && <div className="w-8 h-px bg-gray-700" />}
                </div>
              )
            })}
            <span className="text-gray-400 text-sm ml-2">
              {currentPart === 'part1' ? 'Personal Questions' : currentPart === 'part2' ? 'Long Turn' : 'Discussion'}
            </span>
          </div>

          {currentPart === 'part1' && (
            <div className="space-y-4">
              <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
                <h2 className="text-lg font-semibold text-white mb-1">Part 1 — Personal Questions</h2>
                <p className="text-gray-400 text-sm mb-4">Answer each question naturally. Aim for 2-3 sentences.</p>
                <div className="space-y-5">
                  {prompt.part1.questions.map((q, i) => (
                    <div key={i}>
                      <p className="text-gray-300 text-sm mb-2"><span className="text-gray-500 mr-1">Q{i+1}.</span>{q}</p>
                      <AudioInput
                        questionKey={'p1_' + i}
                        existingText={part1Responses[String(i)]}
                        onClear={() => setPart1Responses(prev => { const n = {...prev}; delete n[String(i)]; return n })}
                      />
                    </div>
                  ))}
                </div>
              </div>
              <button onClick={() => setCurrentPart('part2')} disabled={!p1Done}
                className="w-full py-3 bg-brand-500 hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors">
                Continue to Part 2 →
              </button>
            </div>
          )}

          {currentPart === 'part2' && (
            <div className="space-y-4">
              <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
                <h2 className="text-lg font-semibold text-white mb-1">Part 2 — Long Turn</h2>
                <p className="text-gray-400 text-sm mb-4">Read the cue card, prepare for 1 minute, then speak for 1-2 minutes.</p>
                <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4 mb-4">
                  <p className="text-blue-300 text-sm font-medium mb-2">📋 Cue Card</p>
                  <p className="text-gray-300 text-sm whitespace-pre-line">{prompt.part2.cue_card}</p>
                </div>
                <AudioInput questionKey="p2" existingText={part2Response} onClear={() => setPart2Response('')} />
              </div>
              <div className="flex gap-3">
                <button onClick={() => setCurrentPart('part1')} className="px-6 py-3 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-xl transition-colors">← Back</button>
                <button onClick={() => setCurrentPart('part3')} disabled={!p2Done}
                  className="flex-1 py-3 bg-brand-500 hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors">
                  Continue to Part 3 →
                </button>
              </div>
            </div>
          )}

          {currentPart === 'part3' && (
            <div className="space-y-4">
              <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
                <h2 className="text-lg font-semibold text-white mb-1">Part 3 — Discussion</h2>
                <p className="text-gray-400 text-sm mb-4">Give extended answers. Support your views with reasons and examples.</p>
                <div className="space-y-5">
                  {prompt.part3.questions.map((q, i) => (
                    <div key={i}>
                      <p className="text-gray-300 text-sm mb-2"><span className="text-gray-500 mr-1">Q{i+1}.</span>{q}</p>
                      <AudioInput
                        questionKey={'p3_' + i}
                        existingText={part3Responses[String(i)]}
                        onClear={() => setPart3Responses(prev => { const n = {...prev}; delete n[String(i)]; return n })}
                      />
                    </div>
                  ))}
                </div>
              </div>
              <div className="flex gap-3">
                <button onClick={() => setCurrentPart('part2')} className="px-6 py-3 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-xl transition-colors">← Back</button>
                <button onClick={handleSubmit} disabled={submitting || !p3Done}
                  className="flex-1 flex items-center justify-center gap-2 py-3 bg-brand-500 hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors">
                  {submitting ? <><Loader2 className="w-4 h-4 animate-spin" /> Getting examiner feedback...</> : <>Submit for feedback 🎤</>}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* RESULTS phase */}
      {phase === 'results' && results && (
        <div className="space-y-6">
          <h2 className="text-xl font-bold text-white">Speaking Test Results</h2>

          {ttsUrl ? (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <Volume2 className="w-5 h-5 text-brand-400" />
                <span className="text-white font-medium">Listen to your examiner feedback</span>
              </div>
              <audio controls className="w-full" src={ttsUrl}>Your browser does not support audio.</audio>
            </div>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 flex items-center gap-3">
              <Loader2 className="w-5 h-5 text-brand-400 animate-spin flex-shrink-0" />
              <span className="text-gray-400 text-sm">Generating spoken feedback...</span>
            </div>
          )}

          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
            <h3 className="text-base font-semibold text-white mb-3">💬 Examiner Feedback</h3>
            <p className="text-gray-300 leading-relaxed">{results.feedback_text}</p>
          </div>

          {results.scores && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
              <h3 className="text-base font-semibold text-white mb-4">Band Scores</h3>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                {[
                  { key: 'fluency_coherence',   label: 'Fluency & Coherence' },
                  { key: 'lexical_resource',     label: 'Lexical Resource' },
                  { key: 'grammatical_range',    label: 'Grammatical Range' },
                  { key: 'pronunciation_clarity', label: 'Pronunciation' },
                ].map(({ key, label }) => (
                  <div key={key} className="text-center">
                    <div className={`text-3xl font-bold mb-1 ${
                      (results.scores[key] || 0) >= 7 ? 'text-green-400' :
                      (results.scores[key] || 0) >= 5 ? 'text-yellow-400' : 'text-red-400'
                    }`}>
                      {results.scores[key] || '—'}<span className="text-gray-600 text-lg">/9</span>
                    </div>
                    <p className="text-gray-500 text-xs">{label}</p>
                  </div>
                ))}
              </div>
              {results.scores.overall_band && (
                <div className="text-center py-3 bg-brand-500/10 border border-brand-500/30 rounded-xl">
                  <p className="text-gray-400 text-sm">Overall Band</p>
                  <p className="text-brand-400 text-4xl font-bold">{results.scores.overall_band}</p>
                </div>
              )}
            </div>
          )}

          <button
            onClick={loadPrompt}
            className="px-6 py-3 bg-brand-500 hover:bg-brand-600 text-white font-semibold rounded-xl transition-colors"
          >
            Next topic →
          </button>
        </div>
      )}
    </div>
  )
}
