'use client';

import Link from 'next/link';
import styles from '@/components/people/PublicPerson.module.css';

export default function PersonError() {
    return <section className={styles.page}>
        <Link href="/" className={styles.back}>← На главную</Link>
        <div className={styles.message} role="alert">
            <h1>Не удалось загрузить профиль</h1>
            <p>Повторите попытку, когда соединение восстановится.</p>
            <button type="button" className={styles.retry} onClick={()=>window.location.reload()}>Повторить</button>
        </div>
    </section>;
}
