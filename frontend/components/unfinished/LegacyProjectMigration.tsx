'use client';

import { useLegacyProjectMigration } from '@/hooks/projects/useLegacyProjectMigration';
import { ApiError } from '@/lib/api/http';
import styles from './UnfinishedSurface.module.css';

function errorMessage(error: unknown) {
    if (error instanceof ApiError) {
        if (error.status === 410) return 'Этот перенос уже был удалён из аккаунта. Автоматическое восстановление отключено; локальная копия сохранена.';
        if (error.status === 404) return 'Исходный товар больше недоступен. Локальная копия сохранена.';
        if (error.status === 422) return 'Формат проекта или его изображения не поддерживаются. Локальная копия сохранена.';
        return 'Не удалось подтвердить перенос. Проверьте соединение и повторите попытку. Локальная копия сохранена.';
    }
    return error instanceof Error && /[а-яА-Я]/.test(error.message) ? error.message
        : 'Не удалось подтвердить перенос. Проверьте соединение и повторите попытку. Локальная копия сохранена.';
}

export default function LegacyProjectMigration({ accountEmail, onClose }: { accountEmail: string; onClose: () => void }) {
    const migration = useLegacyProjectMigration();
    return (
        <section className={styles.profileSettingsCard} aria-label="Перенос локальных проектов">
            <h2>Старые проекты в этом браузере</h2>
            <p className={styles.profileMessage}>Аккаунт назначения: <strong>{accountEmail}</strong></p>
            <p className={styles.profileMessage}>Выберите записи, которые принадлежат вам. После переноса они будут доступны на других устройствах. Локальные копии сохраняются; убрать их можно отдельным действием.</p>
            <button type="button" className={styles.profileAccountAction} disabled={migration.busy} onClick={migration.refresh}>Обновить локальный список</button>
            {!migration.entries.length && !migration.issues.length && <p role="status" className={styles.profileMessage}>Старых проектов в этом браузере нет.</p>}
            <ul className={styles.migrationList}>
                {migration.entries.map(entry => {
                    const result = migration.results[entry.key];
                    return <li key={entry.key} className={styles.migrationRow}>
                        <label className={styles.migrationChoice}>
                            <input type="checkbox" disabled={migration.busy} checked={migration.selected.has(entry.key)} onChange={() => migration.toggle(entry.key)} />
                            <span>{entry.item.name}<small>{entry.item.kind === 'draft' ? 'Черновик' : 'Коллекция'} · Товар #{entry.item.productId}</small></span>
                        </label>
                        {result?.receipt && <>
                            <p className={styles.profileMessage} role="status">Сохранён в аккаунте. Локальная копия пока здесь.</p>
                            <a className={styles.profileAccountAction} href={`/constructor?projectId=${result.receipt.id}`}>Открыть серверный проект #{result.receipt.id}</a>
                            <button className={styles.profileAccountAction} type="button" disabled={migration.busy} onClick={() => void migration.removeLocalCopy(entry)}>Убрать локальную копию</button>
                        </>}
                        {Boolean(result?.error) && <p role="alert" className={styles.profileMessage}>{errorMessage(result?.error)}</p>}
                    </li>;
                })}
                {migration.issues.map(issue => <li key={issue.key} className={styles.migrationRow}>
                    <span>{issue.title}</span><p className={styles.profileMessage}>{issue.reason}</p>
                </li>)}
            </ul>
            {migration.notice && <p role="status" className={styles.profileMessage}>{migration.notice}</p>}
            {migration.entries.length > 0 && <button className={styles.profilePrimaryButton} type="button" disabled={migration.busy || migration.selected.size === 0} onClick={() => void migration.importSelected()}>
                {migration.busy ? 'Переносим…' : 'Перенести выбранные проекты'}
            </button>}
            <button className={styles.profileAccountAction} type="button" onClick={onClose}>{migration.busy ? 'Остановить и вернуться в профиль' : 'Вернуться в профиль'}</button>
        </section>
    );
}
