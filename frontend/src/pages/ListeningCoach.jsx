import { useState, useEffect } from 'react'
import {
  getListeningTracks,
  getListeningTrack,
  getListeningMemories,
  getTrackAudioUrl,
  submitListening,
} from '../api/listening'
import { Headphones, ChevronRight, Loader2, Brain, CheckCircle } from 'lucide-react'

const TYPE_LABELS = {
  multiple_choice: 'Multiple Choice',
  form_completion: 'Form Completion',
  short_answer: 'Short Answer',
}

export default function ListeningCoach() {
  const [phase, setPhase] = useState('selection')
  const [tracks, setTracks] = useState([])
  const [track, setTrack] = useState(null)
  const [memories, setMemories] = useState([])
  const [answers, setAnswers] = useState({})
  const [results, setResults] = useState(null)
  const [audioUrl, setAudioUrl] = useState(null)
  const [audioReady, setAudioReady] = useState(false)
  const [loading, setLoading] = useState(true)
  const [generatingAudio, setGeneratingAudio] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([getListeningTracks(), getListeningMemories()])
      .then(([tRes, mRes]) => {
        setTracks(tRes.data.tracks || [])
        setMemories(mRes.data.memories || [])
      })
      .catch(() => setError('Could not load listening tracks.'))
      .finally(() => setLoading(false))
  }, [])

  const selectTrack = async (id) => {
    setLoading(true)
    try {
      const res = await getListeningTrack(id)
      setTrack(res.data.track)
      setAnswers({})
      setResults(null)
      setAudioUrl(null)
      setAudioReady(false)
      setPhase('preview')
      generateAudio(id)
    } catch {
      setError('Could not load track.')
    } finally {
      setLoading(false)
    }
  }

  const generateAudio = async (trackId) => {
    setGeneratingAudio(true)
    try {
      const token = localStorage.getItem('token')
      const url = getTrackAudioUrl(trackId)
      const response = await fetch(url, {
        headers: { Authorization: 'Bearer ' + token },
      })
      if (!response.ok) throw new Error('Audio generation failed')
      const blob = await response.blob()
      const objectUrl = URL.createObjectURL(blob)
      setAudioUrl(objectUrl)
      setAudioReady(true)
    } catch (err) {
      setError('Could not generate audio. Please try again.')
    } finally {
      setGeneratingAudio(false)
    }
  }

  const handleAnswer = (qid, value) => {
    setAnswers((prev) => ({ ...prev, [qid]: value }))
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    setError('')
    try {
      const res = await submitListening({
        track_id: track.track_id,
        answers,
      })
      setResults(res.data)
      setPhase('results')
    } catch (err) {
      setError(err.response?.data?.detail || 'Submission failed.')
    } finally {
      setSubmitting(false)
    }
  }

  const resetSession = () => {
    setPhase('selection')
    setTrack(null)
    setAnswers({})
    setResults(null)
    setAudioUrl(null)
    setAudioReady(false)
    setError('')
  }

  const totalQuestions = track ? track.questions.length : 0
  const answeredCount = Object.keys(answers).length

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
      </div>
    )
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Headphones className="w-6 h-6 text-yellow-400" />
            Listening Coach
          </h1>
          <p className="text-gray-400 mt-1">
            Preview the questions, then listen once and answer
          </p>
        </div>
        {phase !== 'selection' && (
          <button
            onClick={resetSession}
            className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-xl text-sm transition-colors"
          >
            ← Choose different track
          </button>
        )}
      </div>

      {memories.length > 0 && phase === 'selection' && (
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

      {phase === 'selection' && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-white">Choose a track</h2>
          {tracks.map((t) => (
            <button
              key={t.track_id}
              onClick={() => selectTrack(t.track_id)}
              className="w-full text-left bg-gray-900 border border-gray-800 hover:border-gray-700 rounded-2xl p-5 transition-colors group"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-medium px-2 py-0.5 rounded-lg bg-yellow-500/15 text-yellow-400">
                      Part {t.part}
                    </span>
                    <span className={
                      'text-xs font-medium px-2 py-0.5 rounded-lg ' +
                      (t.difficulty === 'beginner' ? 'bg-green-500/15 text-green-400' :
                       t.difficulty === 'intermediate' ? 'bg-yellow-500/15 text-yellow-400' :
                       'bg-red-500/15 text-red-400')
                    }>
                      {t.difficulty}
                    </span>
                  </div>
                  <p className="text-white font-medium">{t.title}</p>
                  <p className="text-gray-500 text-sm mt-1">{t.question_count} questions</p>
                </div>
                <ChevronRight className="w-5 h-5 text-gray-600 group-hover:text-gray-400 flex-shrink-0" />
              </div>
            </button>
          ))}
        </div>
      )}

      {phase === 'preview' && track && (
        <div className="grid lg:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
              <h2 className="text-base font-semibold text-white mb-1">
                Part {track.part}: {track.title}
              </h2>
              <p className="text-gray-400 text-sm">{track.context}</p>
            </div>

            <div className="bg-brand-500/10 border border-brand-500/30 rounded-2xl p-5">
              <h3 className="text-brand-400 font-medium mb-2">📝 IELTS Strategy</h3>
              <ul className="space-y-1.5 text-gray-400 text-sm">
                <li>• Read ALL questions carefully before listening</li>
                <li>• Underline key words in each question</li>
                <li>• Think about what type of answer is needed</li>
                <li>• Listen for synonyms — the audio may rephrase</li>
                <li>• The audio plays ONCE — stay focused</li>
              </ul>
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4">
              <p className="text-sm font-medium text-gray-300 mb-2">Audio Status</p>
              {generatingAudio ? (
                <div className="flex items-center gap-2 text-gray-400 text-sm">
                  <Loader2 className="w-4 h-4 animate-spin text-brand-500" />
                  Cherry is preparing your audio... Read the questions while you wait.
                </div>
              ) : audioReady ? (
                <div className="flex items-center gap-2 text-green-400 text-sm">
                  <CheckCircle className="w-4 h-4" />
                  Audio is ready! Finish reading then start listening.
                </div>
              ) : null}
            </div>

            <button
              onClick={() => setPhase('listening')}
              disabled={!audioReady}
              className="w-full py-3 bg-brand-500 hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors"
            >
              {audioReady ? '▶️ Start Listening' : 'Preparing audio...'}
            </button>
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
            <h3 className="text-base font-semibold text-white mb-4">
              📝 Read the Questions First
            </h3>
            <div className="space-y-4 max-h-[500px] overflow-y-auto pr-1">
              {track.questions.map((q, i) => (
                <div key={q.question_id} className="border-b border-gray-800 pb-3 last:border-0">
                  <p className="text-xs text-gray-600 mb-1">{TYPE_LABELS[q.question_type]}</p>
                  <p className="text-gray-300 text-sm">
                    <span className="text-gray-500 mr-1">Q{i + 1}.</span>
                    {q.question}
                  </p>
                  {q.question_type === 'multiple_choice' && q.options && (
                    <div className="mt-2 space-y-1">
                      {Object.entries(q.options).map(([k, v]) => (
                        <p key={k} className="text-gray-500 text-xs ml-3">
                          {k}: {v}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {phase === 'listening' && track && audioUrl && (
        <div className="space-y-6">
          <div className="bg-red-500/10 border border-red-500/30 rounded-2xl p-4">
            <p className="text-red-300 text-sm font-medium">
              🔴 EXAM CONDITIONS — Press play and answer the questions as you listen. The audio plays once only.
            </p>
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
            <p className="text-white font-medium mb-3">🔊 Recording — Play Once</p>
            <audio controls className="w-full" src={audioUrl}>
              Your browser does not support audio.
            </audio>
            <p className="text-gray-500 text-xs mt-2">
              Press play now and answer the questions below as you listen.
            </p>
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
                    <span className="text-gray-500 mr-1">Q{i + 1}.</span>
                    {q.question}
                  </p>
                  <p className="text-xs text-gray-600 mb-2">{TYPE_LABELS[q.question_type]}</p>

                  {q.question_type === 'multiple_choice' && (
                    <div className="space-y-2">
                      {Object.entries(q.options || {}).map(([k, v]) => (
                        <label key={k} className="flex items-center gap-3 cursor-pointer">
                          <input
                            type="radio"
                            name={q.question_id}
                            value={k}
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
                    <input
                      type="text"
                      value={answers[q.question_id] || ''}
                      onChange={(e) => handleAnswer(q.question_id, e.target.value)}
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

      {phase === 'results' && results && (
        <div className="space-y-6">
          <div className={
            'rounded-2xl p-6 border flex items-center justify-between ' +
            (results.percentage >= 80 ? 'bg-green-500/10 border-green-500/30' :
             results.percentage >= 60 ? 'bg-yellow-500/10 border-yellow-500/30' :
             'bg-red-500/10 border-red-500/30')
          }>
            <div>
              <p className="text-white font-bold text-2xl">{results.total_score} / {results.max_score}</p>
              <p className="text-gray-400 mt-1">{results.track_title}</p>
            </div>
            <div className={
              'text-4xl font-bold ' +
              (results.percentage >= 80 ? 'text-green-400' :
               results.percentage >= 60 ? 'text-yellow-400' : 'text-red-400')
            }>
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
                      <span className={acc >= 80 ? 'text-green-400' : acc >= 50 ? 'text-yellow-400' : 'text-red-400'}>
                        {acc}%
                      </span>
                    </div>
                    <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                      <div
                        className={
                          'h-full rounded-full ' +
                          (acc >= 80 ? 'bg-green-500' : acc >= 50 ? 'bg-yellow-500' : 'bg-red-500')
                        }
                        style={{ width: acc + '%' }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-3">
            <h2 className="text-base font-semibold text-white">Question Review</h2>
            {(results.question_results || []).map((q, i) => (
              <div
                key={q.question_id}
                className={
                  'rounded-xl p-4 border ' +
                  (q.is_correct ? 'bg-green-500/5 border-green-500/20' : 'bg-red-500/5 border-red-500/20')
                }
              >
                <div className="flex items-start gap-3">
                  <span className="text-lg flex-shrink-0">{q.is_correct ? '✅' : '❌'}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-gray-300 text-sm font-medium">Q{i + 1}: {q.question}</p>
                    <p className="text-gray-500 text-xs mt-1">
                      Your answer: <span className="text-gray-400">{q.learner_answer || 'No answer'}</span>
                    </p>
                    {!q.is_correct && (
                      <>
                        <p className="text-gray-500 text-xs">
                          Correct: <span className="text-green-400">{q.correct_answer}</span>
                        </p>
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
            onClick={resetSession}
            className="px-6 py-3 bg-brand-500 hover:bg-brand-600 text-white font-semibold rounded-xl transition-colors"
          >
            Try another track →
          </button>
        </div>
      )}
    </div>
  )
}
