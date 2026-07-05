import client from './client'

export const startChat = () => client.get('/chat/start')
export const continueChat = (data) => client.post('/chat/continue', data)