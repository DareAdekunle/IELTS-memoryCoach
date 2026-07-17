import client from './client'

export const getSpeakingPrompts = (difficulty) =>
  client.get('/speaking/prompts', { params: difficulty ? { difficulty } : {} })

export const getRandomSpeakingPrompt = (difficulty) =>
  client.get('/speaking/prompt/random', { params: difficulty ? { difficulty } : {} })

export const getSpeakingPromptById = (id) =>
  client.get(`/speaking/prompt/${id}`)

export const getSpeakingMemories = () =>
  client.get('/speaking/memories')

export const transcribeAudio = async (audioBlob, filename = 'recording.wav') => {
  const formData = new FormData()
  formData.append('audio', audioBlob, filename)
  return client.post('/speaking/transcribe', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export const evaluateSpeaking = (data) =>
  client.post('/speaking/evaluate', data)

export const generateTTS = async (text) => {
  const response = await client.post(
    '/speaking/tts',
    { text },
    { responseType: 'blob' }
  )
  return URL.createObjectURL(response.data)
}
