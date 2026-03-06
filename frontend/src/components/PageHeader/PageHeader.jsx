import styles from './PageHeader.module.css'

export default function PageHeader() {
  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <div className={styles.brand}>
          <span className={styles.logo}>✦</span>
          <span className={styles.name}>AIVOA</span>
        </div>
        <h1 className={styles.title}>Log HCP Interaction</h1>
        <div className={styles.badge}>AI-Assisted</div>
      </div>
    </header>
  )
}
