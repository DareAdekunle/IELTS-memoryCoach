import { useState, useEffect, useRef } from 'react'
import {
  getSpeakingPrompts,
  getSpeakingPromptById,
  getSpeakingMemories,
  transcribeAudio,
  evaluateSpeaking,
  generateTTS,
} from '../api/speaking'
import {
  Mic,
  MicOff,
  Upload,
  CheckCircle,
  Loader2,
  ChevronRight,
  Volume2,
  Brain,
  RefreshCw,
} from 'lucide-react'

export default function SpeakingCoach() {
  const [phase, setPhase] = useState('selection')
  const [prompts, setPrompts] = useState([])
  const [prompt, setPrompt] = useState(null)
  const [memories, setMemories] = useState([])
  const [currentPart, setCurrentPart] = useState('part1')
  const [part1Responses, setPart1Responses] = useState({})
  const [part2Response, setPart2Response] = useState('')
  const [part3Responses, setPart3Responses] = useState({})
  const [results, setResults] = useState(null)
  const [ttsUrl, setTtsUrl] = useState(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [transcribing, setTranscribing] = useState({})
  const [error, setError] = useState('')
  const [recording, setRecording] = useState(null)
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])

  useEffect(() => {
    Promise.all([getSpeakingPrompts(), getSpeakingMemories()])
      .then(([pRes, mRes]) => {
        setPrompts(pRes.data.prompts || [])
        setMemories(mRes.data.memories || [])
      })
      .catch(() => setError('Could not load speaking prompts.'))
      .finally(() => setLoading(false))
  }, [])

  const selectPrompt = async (id) => {
    setLoading(true)
    try {
      const res = await getSpeakingPromptById(id)
      setPrompt(res.data.prompt)
      setPart1Responses({})
      setPart2Response('')
      setPart3Responses({})
      setCurrentPart('part1')
      setPhase('session')
    } catch {
      setError('Could not load prompt.')
    } finally {
      setLoading(false)
    }
  }

  const startRecording = async (key) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      chunksRef.current = []
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mr.ondataavailable = (e) => chunksRef.current.push(e.data)
      mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
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
    setTranscribing((prev) => ({ ...prev, [key]: true }))
    try {
      const res = await transcribeAudio(blob, 'recording.webm')
      const text = res.data.text
      if (key.startsWith('p1_')) {
        const idx = key.replace('p1_', '')
        setPart1Responses((prev) => ({ ...prev, [idx]: text }))
      } else if (key === 'p2') {
        setPart2Response(text)
      } else if (key.startsWith('p3_')) {
        const idx = key.replace('p3_', '')
        setPart3Responses((prev) => ({ ...prev, [idx]: text }))
      }
    } catch (err) {
      const msg = err.response?.data?.detail || 'Please try again.'
      setError('Transcription failed: ' + msg)
    } finally {
      setTranscribing((prev) => ({ ...prev, [key]: false }))
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
      } catch {
        console.log('TTS failed')
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Evaluation failed.')
    } finally {
      setSubmitting(false)
    }
  }

  const resetSession = () => {
    setPhase('selection')
    setPrompt(null)
    setPart1Responses({})
    setPart2Response('')
    setPart3Responses({})
    setResults(null)
    setTtsUrl(null)
    setError('')
  }

  function AudioInput({ questionKey, existingText, onClear }) {
    const isTranscribing = transcribing[questionKey]
    const isRecording = recording === questionKey

    if (isTranscribing) {
      return (
        <div className="flex items-center gap-2 text-gray-400 text-sm bg-gray-800 rounded-xl px-4 py-3">
          <Loader2 className="w-4 h-4 animate-spin" />
          Transcribing your answer...
        </div>
      )
    }

    if (existingText) {
      return (
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-3">
          <div className="flex items-start gap-2 mb-2">
            <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0 mt-0.5" />
            <p className="text-gray-300 text-sm italic">"{existingText}"</p>
          </div>
          <button onClick={onClear} className="text-gray-500 text-xs hover:text-gray-300 transition-colors">
            Redo
          </button>
        </div>
      )
    }

    return (
      <div className="flex items-center gap-3 bg-gray-800 rounded-xl px-4 py-3">
        <button
          onClick={() => (isRecording ? stopRecording() : startRecording(questionKey))}
          className={isRecording
            ? 'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-red-500 text-white animate-pulse'
            : 'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-gray-700 text-gray-300 hover:bg-gray-600'}
        >
          {isRecording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          {isRecording ? 'Stop' : 'Record'}
        </button>
        <span className="text-gray-600 text-sm">or</span>
        <label className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-700 text-gray-300 hover:bg-gray-600 text-sm cursor-pointer transition-colors">
          <Upload className="w-4 h-4" />
          Upload
          <input type="file" accept="audio/*" className="hidden" onChange={(e) => handleFileUpload(e, questionKey)} />
        </label>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
      </div>
    )
  }

  const p1Done = prompt ? Object.keys(part1Responses).length === prompt.part1.questions.length : false
  const p2Done = part2Response !== ''
  const p3Done = prompt ? Object.keys(part3Responses).length === prompt.part3.questions.length : false

  return (
    <div className="p-6 max-w-4xl mx-auto">

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">🎤 Speaking Coach</h1>
          <p className="text-gray-400 mt-1">Complete all 3 parts of the IELTS speaking test</p>
        </div>
        {phase === 'session' && (
          <button
            onClick={resetSession}
            className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-xl text-sm transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Change topic
          </button>
        )}
      </div>

      {memories.length > 0 && phase === 'selection' && (
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 mb-6">
          <div className="flex items-center gap-2 mb-2">
            <Brain className="w-4 h-4 text-green-400" />
            <span className="text-sm font-medium text-gray-300">Coach remembers from your last session</span>
          </div>
          {memories.slice(0, 2).map((mem, i) => (
            <p key={i} className="text-gray-400 text-sm">
              {mem.memory_type === 'weakness' ? '⚠️' : '✅'} {mem.skill}: {mem.memory_text}
            </p>
          ))}
        </div>
      )}

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-6">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {phase === 'selection' && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-white">Choose a topic</h2>
          {prompts.map((p) => (
            <button
              key={p.prompt_set_id}
              onClick={() => selectPrompt(p.prompt_set_id)}
              className="w-full text-left bg-gray-900 border border-gray-800 hover:border-gray-700 rounded-2xl p-5 transition-colors group"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className={
                      'text-xs font-medium px-2 py-0.5 rounded-lg ' +
                      (p.difficulty === 'beginner' ? 'bg-green-500/15 text-green-400' :
                       p.difficulty === 'intermediate' ? 'bg-yellow-500/15 text-yellow-400' :
                       'bg-red-500/15 text-red-400')
                    }>
                      {p.difficulty}
                    </span>
                  </div>
                  <p className="text-white font-medium">{p.topic}</p>
                  <p className="text-gray-500 text-sm mt-1">Part 2: {p.part2_title}</p>
                </div>
                <ChevronRight className="w-5 h-5 text-gray-600 group-hover:text-gray-400 flex-shrink-0" />
              </div>
            </button>
          ))}
        </div>
      )}

      {phase === 'session' && prompt && (
        <div className="space-y-6">
          <div className="flex items-center gap-2">
            {['part1', 'part2', 'part3'].map((partKey, i) => {
              const isActive = currentPart === partKey
              const isDone = (i === 0 && p1Done) || (i === 1 && p2Done) || (i === 2 && p3Done)
              return (
                <div key={partKey} className="flex items-center gap-2">
                  <div className={
                    'w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ' +
                    (isDone ? 'bg-green-500 text-white' : isActive ? 'bg-brand-500 text-white' : 'bg-gray-800 text-gray-500')
                  }>
                    {i + 1}
                  </div>
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
                      <p className="text-gray-300 text-sm mb-2">
                        <span className="text-gray-500 mr-1">Q{i + 1}.</span>{q}
                      </p>
                      <AudioInput
                        questionKey={'p1_' + i}
                        existingText={part1Responses[String(i)]}
                        onClear={() => setPart1Responses((prev) => { const n = { ...prev }; delete n[String(i)]; return n })}
                      />
                    </div>
                  ))}
                </div>
              </div>
              <button
                onClick={() => setCurrentPart('part2')}
                disabled={!p1Done}
                className="w-full py-3 bg-brand-500 hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors"
              >
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
                <AudioInput
                  questionKey="p2"
                  existingText={part2Response}
                  onClear={() => setPart2Response('')}
                />
              </div>
              <div className="flex gap-3">
                <button onClick={() => setCurrentPart('part1')} className="px-6 py-3 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-xl transition-colors">
                  ← Back
                </button>
                <button
                  onClick={() => setCurrentPart('part3')}
                  disabled={!p2Done}
                  className="flex-1 py-3 bg-brand-500 hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors"
                >
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
                      <p className="text-gray-300 text-sm mb-2">
                        <span className="text-gray-500 mr-1">Q{i + 1}.</span>{q}
                      </p>
                      <AudioInput
                        questionKey={'p3_' + i}
                        existingText={part3Responses[String(i)]}
                        onClear={() => setPart3Responses((prev) => { const n = { ...prev }; delete n[String(i)]; return n })}
                      />
                    </div>
                  ))}
                </div>
              </div>
              <div className="flex gap-3">
                <button onClick={() => setCurrentPart('part2')} className="px-6 py-3 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-xl transition-colors">
                  ← Back
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={submitting || !p3Done}
                  className="flex-1 flex items-center justify-center gap-2 py-3 bg-brand-500 hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors"
                >
                  {submitting ? <><Loader2 className="w-4 h-4 animate-spin" /> Getting examiner feedback...</> : <>Submit for feedback 🎤</>}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {phase === 'results' && results && (
        <div className="space-y-6">
          <h2 className="text-xl font-bold text-white">Speaking Test Results</h2>

          {ttsUrl ? (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <Volume2 className="w-5 h-5 text-brand-400" />
                <span className="text-white font-medium">Listen to your examiner feedback</span>
              </div>
              <audio controls className="w-full" src={ttsUrl}>
                Your browser does not support audio playback.
              </audio>
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
                  { key: 'fluency_coherence', label: 'Fluency & Coherence' },
                  { key: 'lexical_resource', label: 'Lexical Resource' },
                  { key: 'grammatical_range', label: 'Grammatical Range' },
                  { key: 'pronunciation_clarity', label: 'Pronunciation' },
                ].map(({ key, label }) => (
                  <div key={key} className="text-center">
                    <div className={
                      'text-3xl font-bold mb-1 ' +
                      ((results.scores[key] || 0) >= 7 ? 'text-green-400' :
                       (results.scores[key] || 0) >= 5 ? 'text-yellow-400' : 'text-red-400')
                    }>
                      {results.scores[key] || '—'}
                      <span className="text-gray-600 text-lg">/9</span>
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
            onClick={resetSession}
            className="px-6 py-3 bg-brand-500 hover:bg-brand-600 text-white font-semibold rounded-xl transition-colors"
          >
            Try another topic →
          </button>
        </div>
      )}
    </div>
  )
}
