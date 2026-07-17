import { useState, useEffect, useCallback } from 'react'
import {
  getListeningTrack,
  getListeningMemories,
  getTrackAudioUrl,
  submitListening,
} from '../api/listening'
import { Headphones, ChevronRight, Loader2, Brain, RefreshCw } from 'lucide-react'

const TYPE_LABELS = {
  multiple_choice: 'Multiple Choice',
  form_completion: 'Form Completion',
  short_answer: 'Short Answer',
}

const DIFF_COLORS = {
  beginner:     'bg-green-500/15 text-green-400',
  intermediate: 'bg-yellow-500/15 text-yellow-400',
  advanced:     'bg-red-500/15 text-red-400',
}

const PART_DESC = {
  1: 'Social conversation',
  2: 'Monologue / announcement',
  3: 'Academic discussion',
  4: 'Lecture / talk',
}

export default function ListeningCoach() {
  const [phase, setPhase]           = useState('loading')  // loading | preview | listening | results
  const [track, setTrack]           = useState(null)
  const [memories, setMemories]     = useState([])
  const [answers, setAnswers]       = useState({})
  const [results, setResults]       = useState(null)
  const [audioUrl, setAudioUrl]     = useState(null)
  const [audioReady, setAudioReady] = useState(false)
  const [loading, setLoading]       = useState(true)
  const [fetching, setFetching]     = useState(false)
  const [generatingAudio, setGeneratingAudio] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError]           = useState('')

  const loadTrack = useCallback(async () => {
    setFetching(true)
    setError('')
    setAnswers({})
    setResults(null)
    setAudioUrl(null)
    setAudioReady(false)

    try {
      // /listening/track/random returns adaptive unseen track
      const [trackRes, memRes] = await Promise.all([
        getListeningTrack('random'),
        getListeningMemories()
      ])
      setTrack(trackRes.data.track)
      setMemories(memRes.data.memories || [])
      setPhase('preview')
      generateAudio(trackRes.data.track.track_id)
    } catch {
      setError('Could not load listening track. Please refresh.')
    } finally {
      setFetching(false)
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadTrack() }, [loadTrack])

  const generateAudio = async (trackId) => {
    setGeneratingAudio(true)
    try {
      const token = localStorage.getItem('token')
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
      const audioEndpoint = `${baseUrl}/listening/audio/${trackId}`

      // Fetch with auth to trigger generation.
      // If the track is OSS-cached, backend returns 307 → OSS signed URL.
      // fetch() follows redirects by default and will receive the OSS audio bytes.
      // We collect them as a blob and create a local object URL.
      // This works for both disk-cached (direct stream) and OSS (redirect) tracks.
      const response = await fetch(audioEndpoint, {
        headers: { Authorization: 'Bearer ' + token }
      })

      if (!response.ok) {
        throw new Error('Audio request failed: ' + response.status)
      }

      const blob = await response.blob()
      setAudioUrl(URL.createObjectURL(blob))
      setAudioReady(true)
    } catch (e) {
      setError('Could not generate audio. Please try again.')
      console.error('Audio error:', e)
    } finally {
      setGeneratingAudio(false)
    }
  }

  const handleAnswer = (qid, value) =>
    setAnswers(prev => ({ ...prev, [qid]: value }))

  const handleSubmit = async () => {
    setSubmitting(true)
    setError('')
    try {
      const res = await submitListening({ track_id: track.track_id, answers })
      setResults(res.data)
      setPhase('results')
    } catch (err) {
      setError(err.response?.data?.detail || 'Submission failed.')
    } finally {
      setSubmitting(false)
    }
  }

  const totalQuestions = track?.questions?.length || 0
  const answeredCount  = Object.keys(answers).length

  if (loading) return (
    <div className="flex items-center justify-center h-96">
      <div className="text-center">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin mx-auto mb-3" />
        <p className="text-gray-400">Loading your listening session...</p>
      </div>
    </div>
  )

  return (
    <div className="p-6 max-w-5xl mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Headphones className="w-6 h-6 text-yellow-400" />
            Listening Coach
          </h1>
          <p className="text-gray-400 mt-1">Preview the questions, then listen once and answer</p>
        </div>
        {phase !== 'loading' && (
          <button
            onClick={loadTrack}
            disabled={fetching}
            className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-300 rounded-xl text-sm transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${fetching ? 'animate-spin' : ''}`} />
            New track
          </button>
        )}
      </div>

      {/* Memory panel */}
      {memories.length > 0 && phase === 'preview' && (
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 mb-6">
          <div className="flex items-center gap-2 mb-2">
            <Brain className="w-4 h-4 text-green-400" />
            <span className="text-sm font-medium text-gray-300">Coach remembers</span>
          </div>
          {memories.map((mem, i) => (
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

      {/* PREVIEW phase */}
      {phase === 'preview' && track && (
        <div className="grid lg:grid-cols-2 gap-6">
          <div className="space-y-4">
            {/* Track info */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs font-medium px-2 py-0.5 rounded-lg bg-yellow-500/15 text-yellow-400">
                  Part {track.part}
                </span>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-lg ${DIFF_COLORS[track.difficulty]}`}>
                  {track.difficulty}
                </span>
              </div>
              <h2 className="text-white font-semibold mb-1">{track.title}</h2>
              <p className="text-gray-400 text-sm">{track.context}</p>
              <p className="text-gray-600 text-xs mt-2">{PART_DESC[track.part]}</p>
            </div>

            {/* Strategy */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
              <p className="text-sm font-medium text-gray-300 mb-2">📝 IELTS Strategy</p>
              <ul className="text-gray-500 text-xs space-y-1">
                <li>• Read ALL questions carefully before listening</li>
                <li>• Underline key words in each question</li>
                <li>• Think about what type of answer is needed</li>
                <li>• Listen for synonyms — the audio may rephrase</li>
                <li>• The audio plays ONCE — stay focused</li>
              </ul>
            </div>

            {/* Audio status */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
              <p className="text-sm font-medium text-gray-300 mb-3">Audio Status</p>
              {generatingAudio ? (
                <div className="flex items-center gap-2 text-gray-400 text-sm">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Preparing audio...
                </div>
              ) : audioReady ? (
                <div className="flex items-center gap-2 text-green-400 text-sm">
                  <span className="w-2 h-2 rounded-full bg-green-400" />
                  Audio ready
                </div>
              ) : (
                <p className="text-red-400 text-sm">Audio unavailable</p>
              )}
            </div>

            <button
              onClick={() => setPhase('listening')}
              disabled={!audioReady}
              className="w-full py-3 bg-brand-500 hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors"
            >
              {audioReady ? '▶️ Start Listening' : 'Preparing audio...'}
            </button>
          </div>

          {/* Questions preview */}
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
            <h3 className="text-base font-semibold text-white mb-4">📝 Read the Questions First</h3>
            <div className="space-y-4 max-h-[500px] overflow-y-auto pr-1">
              {track.questions.map((q, i) => (
                <div key={q.question_id} className="border-b border-gray-800 pb-3 last:border-0">
                  <p className="text-xs text-gray-600 mb-1">{TYPE_LABELS[q.question_type]}</p>
                  <p className="text-gray-300 text-sm">
                    <span className="text-gray-500 mr-1">Q{i + 1}.</span>{q.question}
                  </p>
                  {q.question_type === 'multiple_choice' && q.options && (
                    <div className="mt-2 space-y-1">
                      {Object.entries(q.options).map(([k, v]) => (
                        <p key={k} className="text-gray-500 text-xs ml-3">{k}: {v}</p>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* LISTENING phase */}
      {phase === 'listening' && track && audioUrl && (
        <div className="space-y-6">
          <div className="bg-red-500/10 border border-red-500/30 rounded-2xl p-4">
            <p className="text-red-300 text-sm font-medium">
              🔴 EXAM CONDITIONS — Press play and answer the questions as you listen. The audio plays once only.
            </p>
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
            <p className="text-white font-medium mb-3">🔊 Recording — Play Once</p>
            <audio controls className="w-full" src={audioUrl}>Your browser does not support audio.</audio>
            <p className="text-gray-500 text-xs mt-2">Press play now and answer the questions below as you listen.</p>
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-white">✏️ Answer While Listening</h2>
              <span className="text-sm text-gray-500">{answeredCount} / {totalQuestions} answered</span>
            </div>

            <div className="space-y-5">
              {track.questions.map((q, i) => (
                <div key={q.question_id} className="border-b border-gray-800 pb-4 last:border-0">
                  <p className="text-gray-300 text-sm mb-2">
                    <span className="text-gray-500 mr-1">Q{i + 1}.</span>{q.question}
                  </p>
                  <p className="text-xs text-gray-600 mb-2">{TYPE_LABELS[q.question_type]}</p>

                  {q.question_type === 'multiple_choice' && (
                    <div className="space-y-2">
                      {Object.entries(q.options || {}).map(([k, v]) => (
                        <label key={k} className="flex items-center gap-3 cursor-pointer">
                          <input type="radio" name={q.question_id} value={k}
                            checked={answers[q.question_id] === k}
                            onChange={() => handleAnswer(q.question_id, k)}
                            className="accent-brand-500"
                          />
                          <span className="text-gray-400 text-sm">{k}: {v}</span>
                        </label>
                      ))}
                    </div>
                  )}

                  {(q.question_type === 'form_completion' || q.question_type === 'short_answer') && (
                    <input type="text"
                      value={answers[q.question_id] || ''}
                      onChange={e => handleAnswer(q.question_id, e.target.value)}
                      placeholder={q.question_type === 'form_completion' ? 'Fill in the missing information...' : 'Your answer...'}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-brand-500 transition-colors"
                    />
                  )}
                </div>
              ))}
            </div>

            <button
              onClick={handleSubmit}
              disabled={submitting || answeredCount < totalQuestions}
              className="w-full mt-4 flex items-center justify-center gap-2 py-3 bg-brand-500 hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors"
            >
              {submitting ? <><Loader2 className="w-4 h-4 animate-spin" /> Checking answers...</> : <>Submit Answers ✅</>}
            </button>
          </div>
        </div>
      )}

      {/* RESULTS phase */}
      {phase === 'results' && results && (
        <div className="space-y-6">
          <div className={`rounded-2xl p-6 border flex items-center justify-between ${
            results.percentage >= 80 ? 'bg-green-500/10 border-green-500/30' :
            results.percentage >= 60 ? 'bg-yellow-500/10 border-yellow-500/30' :
            'bg-red-500/10 border-red-500/30'
          }`}>
            <div>
              <p className="text-white font-bold text-2xl">{results.total_score} / {results.max_score}</p>
              <p className="text-gray-400 mt-1">{results.track_title}</p>
            </div>
            <div className={`text-4xl font-bold ${
              results.percentage >= 80 ? 'text-green-400' :
              results.percentage >= 60 ? 'text-yellow-400' : 'text-red-400'
            }`}>
              {results.percentage}%
            </div>
          </div>

          {Object.keys(results.skill_accuracy || {}).length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
              <h2 className="text-base font-semibold text-white mb-4">Skill Breakdown</h2>
              <div className="space-y-3">
                {Object.entries(results.skill_accuracy).map(([skill, acc]) => (
                  <div key={skill}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-400 capitalize">{skill.replace(/_/g, ' ')}</span>
                      <span className={acc >= 80 ? 'text-green-400' : acc >= 50 ? 'text-yellow-400' : 'text-red-400'}>{acc}%</span>
                    </div>
                    <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${acc >= 80 ? 'bg-green-500' : acc >= 50 ? 'bg-yellow-500' : 'bg-red-500'}`} style={{ width: `${acc}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-3">
            <h2 className="text-base font-semibold text-white">Question Review</h2>
            {(results.question_results || []).map((q, i) => (
              <div key={q.question_id} className={`rounded-xl p-4 border ${q.is_correct ? 'bg-green-500/5 border-green-500/20' : 'bg-red-500/5 border-red-500/20'}`}>
                <div className="flex items-start gap-3">
                  <span className="text-lg flex-shrink-0">{q.is_correct ? '✅' : '❌'}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-gray-300 text-sm font-medium">Q{i + 1}: {q.question}</p>
                    <p className="text-gray-500 text-xs mt-1">Your answer: <span className="text-gray-400">{q.learner_answer || 'No answer'}</span></p>
                    {!q.is_correct && (
                      <>
                        <p className="text-gray-500 text-xs">Correct: <span className="text-green-400">{q.correct_answer}</span></p>
                        <p className="text-gray-500 text-xs mt-1 italic">{q.feedback}</p>
                      </>
                    )}
                  </div>
                  <span className="text-xs text-gray-600 flex-shrink-0">{q.score}/{q.max_score}</span>
                </div>
              </div>
            ))}
          </div>

          <button
            onClick={loadTrack}
            className="px-6 py-3 bg-brand-500 hover:bg-brand-600 text-white font-semibold rounded-xl transition-colors"
          >
            Next track →
          </button>
        </div>
      )}
    </div>
  )
}
