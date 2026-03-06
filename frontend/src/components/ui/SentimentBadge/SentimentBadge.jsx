import styles from './SentimentBadge.module.css'

const CONFIG = {
  positive: { emoji: '😊', label: 'Positive', cls: 'positive' },
  neutral:  { emoji: '😐', label: 'Neutral',  cls: 'neutral'  },
  negative: { emoji: '😟', label: 'Negative', cls: 'negative' },
}

export default function SentimentBadge({ sentiment }) {
  const cfg = CONFIG[sentiment] || CONFIG.neutral
  return (
    <span className={`${styles.badge} ${styles[cfg.cls]}`}>
      {cfg.emoji} {cfg.label}
    </span>
  )
}
