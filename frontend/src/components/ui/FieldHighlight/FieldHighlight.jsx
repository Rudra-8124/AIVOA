import styles from './FieldHighlight.module.css'

/**
 * Wraps a form field with an animated highlight ring when the
 * `active` prop is true — indicating the AI just filled this field.
 */
export default function FieldHighlight({ active, children }) {
  return (
    <div className={`${styles.wrapper} ${active ? styles.active : ''}`}>
      {children}
      {active && (
        <span className={styles.badge} title="Auto-filled by AI">✦ AI</span>
      )}
    </div>
  )
}
