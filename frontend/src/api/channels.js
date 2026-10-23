import api from './client'

export const getChannelStatus = () =>
  api.get('/channels/status').then(r => r.data)

export const createLinkCode = (channel) =>
  api.post(`/channels/${channel}/link-code`).then(r => r.data)

export const disconnectChannel = (channel) =>
  api.delete(`/channels/${channel}`).then(r => r.data)
