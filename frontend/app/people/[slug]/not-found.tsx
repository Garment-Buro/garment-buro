import Link from 'next/link';
import styles from '@/components/people/PublicPerson.module.css';

export default function PersonNotFound() {
    return <section className={styles.page}>
        <Link href="/" className={styles.back}>← На главную</Link>
        <div className={styles.message}><h1>Профиль недоступен</h1><p>Возможно, его ещё не опубликовали или скрыли.</p></div>
    </section>;
}
