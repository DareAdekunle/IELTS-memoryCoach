import api from './client'

export const setupSchedule = (data) =>
  api.post('/schedule/setup', data).then(r => r.data)

export const getMySchedule = () =>
  api.get('/schedule/me').then(r => r.data)

export const cancelSchedule = () =>
  api.delete('/schedule/cancel').then(r => r.data)

export const getCalendarConnectUrl = () =>
  api.get('/schedule/calendar/connect').then(r => r.data)

export const disconnectCalendar = () =>
  api.delete('/schedule/calendar/disconnect').then(r => r.data)
