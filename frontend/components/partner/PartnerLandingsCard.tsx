'use client';

import Link from 'next/link';
import { PageCursorExpiredError } from '@/lib/catalog/pagedResource';
import type { useLandingEditor } from '@/hooks/partner/useLandingEditor';
import { PartnerLandingEditor } from './PartnerLandingEditor';
import styles from './PartnerDashboard.module.css';

const statuses = { draft: 'Черновик', published: 'Опубликован', archived: 'В архиве' };
export const PartnerLandingsCard = ({
    editor,
}: {
    editor: ReturnType<typeof useLandingEditor>;
}) => {
    const state = editor.state,
        busy = !state || state.status !== 'ready';
    return (
        <section className={styles.panel} aria-labelledby="partner-landings-title">
            <div className={styles.panelHeader}>
                <div>
                    <p className={styles.sectionEyebrow}>Лендинги и коллекции</p>
                    <h2 id="partner-landings-title">Мои сообщества</h2>
                </div>
                {!state?.editing && (
                    <button
                        type="button"
                        className={styles.secondaryButton}
                        disabled={busy}
                        onClick={editor.createDraft}
                    >
                        Создать сообщество
                    </button>
                )}
            </div>
            {!state?.loaded && !state?.error && <p role="status">Загружаем ваши сообщества…</p>}
            {Boolean(state?.error) && !state?.editing && (
                <p role="alert">
                    {state?.error instanceof PageCursorExpiredError ? 'Список изменился. Обновите его, чтобы продолжить.' : 'Не удалось получить данные сообщества.'}{' '}
                    <button type="button" disabled={busy} onClick={() => void editor.retryList()}>
                        Повторить
                    </button>
                </p>
            )}
            {state?.loaded && !state.items.length && !state.editing && (
                <p className={styles.emptyText}>
                    Создайте лендинг, расскажите о сообществе и выберите модели для коллекции.
                </p>
            )}
            {!state?.editing && (
                <div className={styles.landingList}>
                    {state?.items.map((landing) => (
                        <article className={styles.landingRow} key={landing.id}>
                            <div className={styles.landingInfo}>
                                <p className={styles.landingTitle}>{landing.title}</p>
                                <p className={styles.landingUrl}>
                                    {statuses[landing.status]} · {landing.product_count}{' '}
                                    моделей
                                </p>
                            </div>
                            <div className={styles.landingActions}>
                                <button
                                    type="button"
                                    className={styles.secondaryButton}
                                    disabled={busy}
                                    onClick={() => void editor.open(landing.id)}
                                >
                                    Редактировать
                                </button>
                                {landing.status === 'published' && (
                                    <Link
                                        className={styles.iconButton}
                                        href={`/p/${encodeURIComponent(landing.slug)}`}
                                        prefetch={false}
                                        target="_blank"
                                        rel="noreferrer"
                                        aria-label={`Открыть ${landing.title}`}
                                    >
                                        ↗
                                    </Link>
                                )}
                            </div>
                        </article>
                    ))}
                </div>
            )}
            {!state?.editing && state?.nextCursor && !(state.error instanceof PageCursorExpiredError) && (
                <button
                    type="button"
                    className={styles.secondaryButton}
                    disabled={busy}
                    onClick={() => void editor.more()}
                >
                    Ещё сообщества
                </button>
            )}
            <PartnerLandingEditor editor={editor} />
        </section>
    );
};
