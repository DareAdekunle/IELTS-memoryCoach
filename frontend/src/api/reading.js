import client from './client'

export const getPassages = () => client.get('/reading/passages')
export const getRandomPassage = (difficulty) =>
  client.get('/reading/passage/random', { params: { difficulty } })
export const getPassageById = (id) => client.get(`/reading/passage/${id}`)
export const getReadingMemories = () => client.get('/reading/memories')
export const submitReading = (data) => client.post('/reading/submit', data)