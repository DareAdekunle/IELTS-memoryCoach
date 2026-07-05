import client from './client'

export const getPrompt = () => client.get('/writing/prompt')
export const getWritingMemories = () => client.get('/writing/memories')
export const submitEssay = (data) => client.post('/writing/submit', data)
export const getWritingAttempts = () => client.get('/writing/attempts')