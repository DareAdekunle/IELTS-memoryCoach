import client from './client'

export const getChatContext = (section = 'Writing') =>
  client.get('/chat/context', { params: { section } })

export const startChat = (section = 'Writing') =>
  client.get('/chat/start', { params: { section } })

export const continueChat = (data) =>
  client.post('/chat/continue', data)
