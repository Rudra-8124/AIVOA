import api from './api'

/**
 * Send a chat message to the AI agent.
 * POST /api/ai/chat
 *
 * @param {string} message  – natural language from the user
 * @param {string} sessionId – persistent session UUID
 * @returns {{ reply: string, extracted_fields?: object, intent?: string }}
 */
export async function sendChatMessage(message, sessionId) {
  const { data } = await api.post('/ai/chat', {
    message,
    session_id: sessionId,
  })
  return data
}

/**
 * Log an interaction directly (structured form submit).
 * POST /api/interactions/log
 */
export async function logInteraction(payload) {
  const { data } = await api.post('/interactions/log', payload)
  return data
}
