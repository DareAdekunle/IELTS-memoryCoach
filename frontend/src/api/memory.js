import client from './client'

export const getAllMemories = () => client.get('/memory/all')
export const getActiveMemories = (section) =>
  client.get('/memory/active', { params: { section } })
export const getMemoryStats = () => client.get('/memory/stats')
