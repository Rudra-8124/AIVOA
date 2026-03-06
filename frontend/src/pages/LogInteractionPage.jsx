import styles from './LogInteractionPage.module.css'
import InteractionForm from '../components/InteractionForm/InteractionForm'
import ChatPanel from '../components/ChatPanel/ChatPanel'
import PageHeader from '../components/PageHeader/PageHeader'

export default function LogInteractionPage() {
  return (
    <div className={styles.page}>
      <PageHeader />
      <main className={styles.main}>
        <section className={styles.formColumn} aria-label="Structured form">
          <InteractionForm />
        </section>
        <section className={styles.chatColumn} aria-label="AI assistant">
          <ChatPanel />
        </section>
      </main>
    </div>
  )
}
