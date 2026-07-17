import { useState, useEffect, useRef } from 'react'
import {
  getPrompt, getWritingMemories, submitEssayStream
} from '../api/writing'
import {
  PenLine, RefreshCw, Brain, ChevronRight,
  Loader2, Upload, Camera, X, CheckCircle
} from 'lucide-react'

const SKILL_LABELS = {
  thesis_clarity:   'Thesis Clarity',
  organization:     'Organization',
  grammar:          'Grammar',
  vocabulary:       'Vocabulary',
  idea_development: 'Idea Development'
}

export default function WritingCoach() {
  const [prompt, setPrompt]               = useState(null)
  const [memories, setMemories]           = useState([])
  const [essay, setEssay]                 = useState('')
  const [loading, setLoading]             = useState(true)
  const [submitting, setSubmitting]       = useState(false)
  const [feedback, setFeedback]           = useState(null)
  const [streamingText, setStreamingText] = useState('')
  const [isStreaming, setIsStreaming]     = useState(false)
  const [error, setError]                 = useState('')
  const [inputMode, setInputMode]         = useState('text') // 'text' | 'image'
  const [imageFile, setImageFile]         = useState(null)
  const [imagePreview, setImagePreview]   = useState(null)
  const [extractedText, setExtractedText] = useState(null)
  const [extractionMeta, setExtractionMeta] = useState(null)
  const fileInputRef = useRef(null)

  useEffect(() => { loadPromptAndMemories() }, [])

  const loadPromptAndMemories = async () => {
    setLoading(true)
    setFeedback(null)
    setEssay('')
    setError('')
    setStreamingText('')
    setIsStreaming(false)
    setImageFile(null)
    setImagePreview(null)
    setExtractedText(null)
    setExtractionMeta(null)
    try {
      const [promptRes, memRes] = await Promise.all([
        getPrompt(), getWritingMemories()
      ])
      setPrompt(promptRes.data)
      setMemories(memRes.data.memories || [])
    } catch {
      setError('Could not load writing prompt. Please refresh.')
    } finally {
      setLoading(false)
    }
  }

  const handleImageSelect = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImageFile(file)
    const url = URL.createObjectURL(file)
    setImagePreview(url)
    setExtractedText(null)
    setExtractionMeta(null)
  }

  const clearImage = () => {
    setImageFile(null)
    setImagePreview(null)
    setExtractedText(null)
    setExtractionMeta(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleSubmitImage = async () => {
    if (!imageFile || !prompt) return
    setSubmitting(true)
    setError('')

    try {
      const formData = new FormData()
      formData.append('image', imageFile)
      formData.append('prompt', prompt.prompt)
      formData.append('task_type', prompt.task_type)

      const token = localStorage.getItem('token')
      const res = await fetch('/api/writing/submit/image', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Image submission failed')
      }

      const result = await res.json()
      setExtractedText(result.extracted_text)
      setExtractionMeta({
        confidence: result.extraction_confidence,
        notes: result.extraction_notes,
        word_count: result.word_count
      })
      setFeedback(result)
    } catch (e) {
      setError(e.message || 'Could not process image. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleSubmit = async () => {
    if (!prompt || essay.trim().length < 50) return
    setSubmitting(true)
    setIsStreaming(true)
    setStreamingText('')
    setFeedback(null)
    setError('')

    await submitEssayStream(
      { prompt: prompt.prompt, task_type: prompt.task_type, essay: essay.trim() },
      (token) => setStreamingText(prev => prev + token),
      (result) => { setFeedback(result); setIsStreaming(false); setSubmitting(false); setStreamingText('') },
      (err) => { setError(err); setIsStreaming(false); setSubmitting(false); setStreamingText('') }
    )
  }

  const wordCount = essay.trim() ? essay.trim().split(/\s+/).length : 0

  const DIFFICULTY_LABELS = { beginner: '🟢 Beginner', intermediate: '🟡 Intermediate', advanced: '🔴 Advanced' }

  if (loading) return (
    <div className="flex items-center justify-center h-96">
      <div className="text-center">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin mx-auto mb-3" />
        <p className="text-gray-400">Loading your writing session...</p>
      </div>
    </div>
  )

  return (
    <div className="p-6 max-w-5xl mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <PenLine className="w-6 h-6 text-purple-400" />
            Writing Coach
          </h1>
          <p className="text-gray-400 mt-1">Practice IELTS writing and get personalised AI feedback</p>
        </div>
        <button
          onClick={loadPromptAndMemories}
          className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-xl text-sm transition-colors"
        >
          <RefreshCw className="w-4 h-4" />New prompt
        </button>
      </div>

      {/* Memory panel */}
      {memories.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 mb-6">
          <div className="flex items-center gap-2 mb-3">
            <Brain className="w-4 h-4 text-green-400" />
            <span className="text-sm font-medium text-gray-300">What your coach remembers</span>
          </div>
          <div className="space-y-2">
            {memories.map((mem, i) => (
              <div key={i} className="flex items-start gap-2">
                <span className="text-sm mt-0.5">{mem.memory_type === 'weakness' ? '⚠️' : '✅'}</span>
                <p className="text-gray-400 text-sm">
                  <span className="text-gray-300 font-medium">{mem.skill}:</span> {mem.memory_text}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Essay input phase */}
      {!feedback && !isStreaming && (
        <>
          {/* Prompt card */}
          {prompt && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 mb-6">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs font-medium px-2.5 py-1 rounded-lg bg-purple-500/15 text-purple-400">
                  {prompt.task_type}
                </span>
                <span className="text-xs font-medium px-2.5 py-1 rounded-lg bg-gray-800 text-gray-400">
                  {DIFFICULTY_LABELS[prompt.difficulty] || prompt.difficulty}
                </span>
                <span className="text-xs text-gray-600 ml-auto">Adapted to your level</span>
              </div>
              <p className="text-white leading-relaxed">{prompt.prompt}</p>
            </div>
          )}

          {/* Input mode tabs */}
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => setInputMode('text')}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
                inputMode === 'text'
                  ? 'bg-purple-500/15 text-purple-400 border border-purple-500/30'
                  : 'bg-gray-800 text-gray-400 hover:text-white'
              }`}
            >
              ✍️ Type essay
            </button>
            <button
              onClick={() => setInputMode('image')}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
                inputMode === 'image'
                  ? 'bg-purple-500/15 text-purple-400 border border-purple-500/30'
                  : 'bg-gray-800 text-gray-400 hover:text-white'
              }`}
            >
              <span className="flex items-center gap-1.5">
                <Camera className="w-4 h-4" />Upload handwritten essay
              </span>
            </button>
          </div>

          {/* Text input */}
          {inputMode === 'text' && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
              <div className="flex items-center justify-between mb-3">
                <label className="text-sm font-medium text-gray-300">Your response</label>
                <span className={`text-sm ${wordCount >= 250 ? 'text-green-400' : wordCount > 0 ? 'text-yellow-400' : 'text-gray-500'}`}>
                  {wordCount} / 250 words minimum
                </span>
              </div>
              <textarea
                value={essay}
                onChange={e => setEssay(e.target.value)}
                placeholder="Write your essay here. Aim for at least 250 words..."
                className="w-full h-72 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-brand-500 transition-colors resize-none text-sm leading-relaxed"
              />
              {error && (
                <div className="mt-3 bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                  <p className="text-red-400 text-sm">{error}</p>
                </div>
              )}
              <div className="flex items-center justify-between mt-4">
                <div>
                  {wordCount > 0 && wordCount < 250 && (
                    <p className="text-yellow-400 text-sm">{250 - wordCount} more words needed</p>
                  )}
                  {wordCount >= 250 && (
                    <p className="text-green-400 text-sm">✓ Word count looks good!</p>
                  )}
                </div>
                <button
                  onClick={handleSubmit}
                  disabled={submitting || wordCount < 50}
                  className="flex items-center gap-2 px-6 py-3 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors"
                >
                  {submitting
                    ? <><Loader2 className="w-4 h-4 animate-spin" /> Evaluating...</>
                    : <>Submit for feedback <ChevronRight className="w-4 h-4" /></>
                  }
                </button>
              </div>
            </div>
          )}

          {/* Image upload */}
          {inputMode === 'image' && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
              <p className="text-gray-400 text-sm mb-4">
                Photograph your handwritten essay and upload it. qwen-vl will extract the text
                and evaluate it using the same AI pipeline as typed essays.
              </p>

              {!imagePreview ? (
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed border-gray-700 rounded-xl p-12 text-center cursor-pointer hover:border-gray-500 transition-colors"
                >
                  <Upload className="w-10 h-10 text-gray-600 mx-auto mb-3" />
                  <p className="text-gray-400 font-medium mb-1">Click to upload image</p>
                  <p className="text-gray-600 text-sm">JPEG, PNG or WebP — make sure the text is clearly legible</p>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="hidden"
                    onChange={handleImageSelect}
                  />
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="relative">
                    <img
                      src={imagePreview}
                      alt="Essay preview"
                      className="w-full max-h-80 object-contain rounded-xl border border-gray-700"
                    />
                    <button
                      onClick={clearImage}
                      className="absolute top-2 right-2 w-8 h-8 rounded-full bg-gray-900 border border-gray-700 flex items-center justify-center hover:bg-gray-800 transition-colors"
                    >
                      <X className="w-4 h-4 text-gray-400" />
                    </button>
                  </div>

                  {error && (
                    <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                      <p className="text-red-400 text-sm">{error}</p>
                    </div>
                  )}

                  <div className="flex justify-end">
                    <button
                      onClick={handleSubmitImage}
                      disabled={submitting}
                      className="flex items-center gap-2 px-6 py-3 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors"
                    >
                      {submitting
                        ? <><Loader2 className="w-4 h-4 animate-spin" /> Extracting & evaluating...</>
                        : <>Extract & evaluate <ChevronRight className="w-4 h-4" /></>
                      }
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* Streaming preview */}
      {isStreaming && (
        <div className="bg-gray-900 border border-brand-500/30 rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-2 h-2 rounded-full bg-brand-500 animate-pulse" />
            <span className="text-brand-400 text-sm font-medium">Your coach is writing feedback...</span>
          </div>
          <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap min-h-[60px]">
            {streamingText}
            <span className="inline-block w-0.5 h-4 bg-brand-500 animate-pulse ml-0.5 align-middle" />
          </p>
        </div>
      )}

      {/* Full feedback */}
      {feedback && !isStreaming && (
        <div className="space-y-6">

          {/* Extraction info (image submissions only) */}
          {extractionMeta && (
            <div className="bg-blue-500/5 border border-blue-500/20 rounded-2xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="w-4 h-4 text-blue-400" />
                <span className="text-blue-400 text-sm font-medium">
                  Handwriting extracted — {extractionMeta.word_count} words
                  · Confidence: {extractionMeta.confidence}
                </span>
              </div>
              {extractionMeta.notes && (
                <p className="text-gray-500 text-xs">{extractionMeta.notes}</p>
              )}
              {extractedText && (
                <details className="mt-2">
                  <summary className="text-gray-500 text-xs cursor-pointer hover:text-gray-400">
                    View extracted text
                  </summary>
                  <p className="text-gray-400 text-xs mt-2 leading-relaxed whitespace-pre-wrap">
                    {extractedText}
                  </p>
                </details>
              )}
            </div>
          )}

          {/* Overall feedback */}
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
            <h2 className="text-lg font-semibold text-white mb-3">📊 Overall Feedback</h2>
            <p className="text-gray-300 leading-relaxed">{feedback.overall_feedback}</p>
          </div>

          {/* Scores */}
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
            <h2 className="text-lg font-semibold text-white mb-4">Skill Scores</h2>
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
              {Object.entries(feedback.scores || {}).map(([key, score]) => (
                <div key={key} className="text-center">
                  <div className={`text-3xl font-bold mb-1 ${score >= 4 ? 'text-green-400' : score >= 3 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {score}<span className="text-gray-600 text-lg">/5</span>
                  </div>
                  <p className="text-gray-500 text-xs">{SKILL_LABELS[key] || key}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Strengths and weaknesses */}
          <div className="grid md:grid-cols-2 gap-6">
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
              <h2 className="text-base font-semibold text-green-400 mb-3">✅ Strengths</h2>
              <ul className="space-y-2">
                {(feedback.strengths || []).map((s, i) => (
                  <li key={i} className="text-gray-300 text-sm flex items-start gap-2">
                    <span className="text-green-500 mt-0.5 flex-shrink-0">•</span>{s}
                  </li>
                ))}
              </ul>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
              <h2 className="text-base font-semibold text-yellow-400 mb-3">⚠️ Areas to Improve</h2>
              <ul className="space-y-2">
                {(feedback.weaknesses || []).map((w, i) => (
                  <li key={i} className="text-gray-300 text-sm flex items-start gap-2">
                    <span className="text-yellow-500 mt-0.5 flex-shrink-0">•</span>{w}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {feedback.recommended_next_step && (
            <div className="bg-brand-500/10 border border-brand-500/30 rounded-2xl p-6">
              <h2 className="text-base font-semibold text-brand-400 mb-2">🎯 Recommended Next Step</h2>
              <p className="text-gray-300 text-sm leading-relaxed">{feedback.recommended_next_step}</p>
            </div>
          )}

          <div className="flex gap-4">
            <button
              onClick={() => { setFeedback(null); setStreamingText(''); setExtractedText(null); setExtractionMeta(null) }}
              className="px-6 py-3 bg-gray-800 hover:bg-gray-700 text-white rounded-xl transition-colors"
            >
              Try same prompt again
            </button>
            <button
              onClick={loadPromptAndMemories}
              className="px-6 py-3 bg-brand-500 hover:bg-brand-600 text-white font-semibold rounded-xl transition-colors"
            >
              New prompt →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
