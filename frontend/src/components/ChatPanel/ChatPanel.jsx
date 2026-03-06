import { useRef, useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { sendMessage, clearError } from '../../slices/agentSlice'
import ChatMessage from '../ui/ChatMessage/ChatMessage'
import ExtractedFieldsPreview from '../ui/ExtractedFieldsPreview/ExtractedFieldsPreview'
import styles from './ChatPanel.module.css'

export default function ChatPanel() {
  const dispatch = useDispatch()
  const { messages, loading, error, sessionId } = useSelector((s) => s.agent)
  const [input, setInput] = useState('')
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function handleSend() {
    const text = input.trim()
    if (!text || loading) return

    setInput('')
    dispatch(clearError())
    // sendMessage thunk: adds user message, calls API, patches form, adds reply
    await dispatch(sendMessage({ text, sessionId }))
    inputRef.current?.focus()
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const isEmpty = messages.length === 0

  return (
    <div className={styles.panel}>
      {/* Panel header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.aiDot} aria-hidden="true" />
          <span className={styles.headerTitle}>AI Assistant</span>
        </div>
        <span className={styles.headerHint}>Auto-fills form fields</span>
      </div>

      {/* Message list */}
      <div className={styles.messages}>
        {isEmpty && (
          <div className={styles.emptyState}>
            <div className={styles.emptyIcon}>✦</div>
            <p className={styles.emptyTitle}>Describe the interaction</p>
            <p className={styles.emptySubtitle}>
              Tell me what happened — I'll extract the details and fill the form.
            </p>
            <div className={styles.exampleChips}>
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  className={styles.exampleChip}
                  onClick={() => setInput(ex)}
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id}>
            <ChatMessage message={msg} />
            {msg.role === 'assistant' && msg.extractedFields && (
              <ExtractedFieldsPreview fields={msg.extractedFields} />
            )}
          </div>
        ))}

        {loading && (
          <div className={styles.typingIndicator}>
            <span /><span /><span />
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Error strip */}
      {error && (
        <div className={styles.errorStrip}>
          ❌ {error}
        </div>
      )}

      {/* Input bar */}
      <div className={styles.inputBar}>
        <textarea
          ref={inputRef}
          className={styles.textarea}
          rows={2}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="e.g. Met Dr. Patel today, discussed Cardivex for hypertension, positive response…"
          disabled={loading}
        />
        <button
          className={styles.sendBtn}
          onClick={handleSend}
          disabled={!input.trim() || loading}
          aria-label="Send message"
        >
          {loading ? (
            <span className={styles.spinner} aria-hidden="true" />
          ) : (
            <SendIcon />
          )}
        </button>
      </div>
    </div>
  )
}

const EXAMPLES = [
  'Met Dr. Kim at City Hospital, discussed Cardivex for hypertension — very positive',
  'Called Dr. Patel about Neurostat side effects, she seemed concerned',
  'Emailed Dr. Lee the Cardivex Phase III reprint, follow up in 2 weeks',
]

function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  )
}
