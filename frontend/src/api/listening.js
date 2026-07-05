import client from './client'

export const getListeningTracks = (params) =>
  client.get('/listening/tracks', { params })

export const getListeningTrack = (id) =>
  client.get(`/listening/track/${id}`)

export const getListeningMemories = () =>
  client.get('/listening/memories')

export const getTrackAudioUrl = (trackId) =>
  `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/listening/audio/${trackId}`

export const submitListening = (data) =>
  client.post('/listening/submit', data)