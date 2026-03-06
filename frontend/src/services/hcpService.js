import api from './api'

/**
 * Search HCP directory.
 * GET /api/hcp?search=<query>&limit=20
 *
 * @param {string} query - Name, specialty, or hospital fragment
 * @param {number} [limit=20]
 * @returns {Promise<{ hcps: object[], total: number }>}
 */
export async function searchHcps(query, limit = 20) {
  const { data } = await api.get('/hcp', { params: { search: query, limit } })
  return data
}

/**
 * Fetch paginated interaction history for a specific HCP.
 * GET /api/interactions/history/<hcpId>?page=1&from_date=...&to_date=...
 *
 * @param {string|number} hcpId
 * @param {{ page?: number, fromDate?: string, toDate?: string }} [params]
 * @returns {Promise<{ interactions: object[], total: number, page: number,
 *                     page_size: number, has_more: boolean }>}
 */
export async function fetchHcpHistory(hcpId, { page = 1, fromDate, toDate } = {}) {
  const params = { page }
  if (fromDate) params.from_date = fromDate
  if (toDate) params.to_date = toDate

  const { data } = await api.get(`/interactions/history/${hcpId}`, { params })
  return data
}
