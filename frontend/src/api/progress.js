import client from './client'

export const getSummary = () => client.get('/progress/summary')
export const getWritingProgress = () => client.get('/progress/writing')
export const getReadingProgress = () => client.get('/progress/reading')
export const getSkillRanks = () => client.get('/progress/skills')
export const createProfile = (data) => client.post('/progress/profile', data)
export const getProfile = () => client.get('/progress/profile')