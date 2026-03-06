import styles from './ChatMessage.module.css'

const ROLE_LABEL = { user: 'You', assistant: 'AI' }

export default function ChatMessage({ message }) {
  const isUser = message.role === 'user'
  const time = new Date(message.timestamp).toLocaleTimeString([], {
    hour: '2-digit', minute: '2-digit',
  })

  return (
    <div className={`${styles.wrapper} ${isUser ? styles.user : styles.assistant}`}>
      <div className={`${styles.avatar} ${isUser ? styles.avatarUser : styles.avatarAI}`}>
        {isUser ? '👤' : '✦'}
      </div>
      <div className={styles.body}>
        <div className={styles.bubble}>
          <p className={styles.text}>{message.content}</p>
        </div>
        <span className={styles.time}>{time}</span>
      </div>
    </div>
  )
}
