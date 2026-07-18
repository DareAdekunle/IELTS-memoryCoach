import client from './client'

export const getCriterionStages = (section = 'Writing') =>
  client.get('/pedagogy/criterion-stages', { params: { section } })

export const getFrameworks = (section = null) =>
  client.get('/pedagogy/frameworks', { params: section ? { section } : {} })
