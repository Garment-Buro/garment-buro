'use client';

import { useRef, useState } from 'react';
import { PiCheckCircle, PiCopy, PiPlus } from 'react-icons/pi';
import { useTechCardDirectory } from '@/hooks/production/useReferenceDirectory';
import { saveAssortment } from '@/lib/api/productionAssortment';
import type { TechCardSummary } from '@/lib/production/techDirectory';
import { AdminFilters } from '../AdminFilters';
import { AssortmentFeedback } from './AssortmentDialog';
import { TechCardEditor } from './TechCardEditor';
import styles from '../ProductionAdmin.module.css';

export function AdminTechCards() {
    const [query, setQuery] = useState('');
    const [activityFilter, setActivityFilter] = useState('');
    const [revisionFilter, setRevisionFilter] = useState('');
    const [sorting, setSorting] = useState('model:asc');
    const [editorCard, setEditorCard] = useState<number | null>(null);
    const [saving, setSaving] = useState(false);
    const [formError, setFormError] = useState('');
    const busyRef = useRef(false);
    const setBusy = (busy: boolean) => {
        busyRef.current = busy;
        setSaving(busy);
    };
    const directory = useTechCardDirectory({
        query,
        active: activityFilter ? activityFilter === 'active' : undefined,
        revision_status: revisionFilter || undefined,
        sort: sorting,
        limit: 24,
    });
    const publish = async (card: TechCardSummary, revision: number) => {
        if (busyRef.current) return;
        setBusy(true);
        setFormError('');
        try {
            await saveAssortment(
                `tech-cards/${card.id}/revisions/${revision}/publish`,
                'POST',
                {},
            );
            void directory.retry();
        } catch (error) {
            setFormError(
                error instanceof Error
                    ? error.message
                    : 'Не удалось опубликовать версию.',
            );
        } finally {
            setBusy(false);
        }
    };
    return (
        <section aria-busy={directory.loading}>
            <fieldset className={styles.adminFields} disabled={saving}>
                <div className={styles.assortmentHeading}>
                    <div>
                        <h3>Технологические карты</h3>
                        <p className={styles.muted}>
                            Последовательность операций, роли, время и стоимость
                            работ.
                        </p>
                    </div>
                    <button onClick={() => setEditorCard(0)}>
                        <PiPlus aria-hidden /> Создать техкарту
                    </button>
                </div>
                <p className={styles.muted}>
                    Новая техкарта создаётся для модели без карты. Для изменений
                    создайте новую версию.
                </p>
                <div className={styles.assortmentFilters}>
                    <label className={styles.assortmentSearch}>
                        Поиск техкарты
                        <input
                            type="search"
                            value={query}
                            placeholder="Код, модель или название"
                            onChange={(event) => setQuery(event.target.value)}
                        />
                    </label>
                    <AdminFilters
                        groups={[
                            {
                                key: 'activity',
                                label: 'Видимость',
                                options: [
                                    ['', 'Все техкарты'],
                                    ['active', 'Активные'],
                                    ['hidden', 'Скрытые'],
                                ],
                            },
                            {
                                key: 'revision',
                                label: 'Последняя версия',
                                options: [
                                    ['', 'Любое состояние'],
                                    ['draft', 'Черновик'],
                                    ['published', 'Опубликована'],
                                    ['archived', 'Архив'],
                                    ['discarded', 'Отклонена'],
                                ],
                            },
                            {
                                key: 'sorting',
                                label: 'Сортировка',
                                options: [
                                    ['model:asc', 'По модели'],
                                    ['code:asc', 'По коду'],
                                    ['revision:desc', 'Сначала новые версии'],
                                    ['revision:asc', 'Сначала ранние версии'],
                                ],
                            },
                        ]}
                        values={{
                            activity: activityFilter,
                            revision: revisionFilter,
                            sorting,
                        }}
                        defaults={{
                            activity: '',
                            revision: '',
                            sorting: 'model:asc',
                        }}
                        onApply={(values) => {
                            setActivityFilter(values.activity);
                            setRevisionFilter(values.revision);
                            setSorting(values.sorting);
                        }}
                    />
                </div>

                {formError && (
                    <p className={styles.error} role="alert">
                        {formError}
                    </p>
                )}
                <AssortmentFeedback
                    loading={directory.loading}
                    error={directory.message}
                    empty={!directory.loading && !directory.items.length}
                />
                <div className={styles.assortmentCards}>
                    {directory.items.map((card) => {
                        const draft = card.draft_revision_number;
                        return (
                            <article
                                className={styles.assortmentCard}
                                key={card.id}
                            >
                                <div className={styles.assortmentCardTop}>
                                    <div>
                                        <span className={styles.badge}>
                                            {card.code}
                                        </span>
                                        <h4>{card.garment_model_name}</h4>
                                    </div>
                                    <span className={styles.badge}>
                                        Версия {card.latest_revision_number}
                                    </span>
                                </div>
                                <p>
                                    {card.latest_revision_name ??
                                        'Без названия'}
                                </p>
                                <p className={styles.muted}>
                                    {card.checkpoint_count} операций ·{' '}
                                    {draft ? 'Есть черновик' : 'Черновика нет'}
                                </p>
                                <div className={styles.cardActions}>
                                    {!draft ? (
                                        <button
                                            onClick={() =>
                                                setEditorCard(card.id)
                                            }
                                        >
                                            <PiCopy aria-hidden /> Новая версия
                                        </button>
                                    ) : (
                                        <button
                                            disabled
                                            title="Сначала опубликуйте текущий черновик"
                                        >
                                            <PiCopy aria-hidden /> Черновик уже
                                            есть
                                        </button>
                                    )}
                                    {draft && (
                                        <button
                                            className={styles.primaryButton}
                                            onClick={() =>
                                                void publish(card, draft)
                                            }
                                        >
                                            <PiCheckCircle aria-hidden />{' '}
                                            Опубликовать
                                        </button>
                                    )}
                                </div>
                            </article>
                        );
                    })}
                </div>
                {(directory.message || formError) && (
                    <button
                        type="button"
                        onClick={() => {
                            setFormError('');
                            void directory.retry();
                        }}
                    >
                        Обновить техкарты
                    </button>
                )}
                {directory.hasMore && (
                    <button
                        type="button"
                        disabled={directory.loadingMore}
                        onClick={() => void directory.loadMore()}
                    >
                        Ещё техкарты
                    </button>
                )}
                {editorCard !== null && (
                    <TechCardEditor
                        key={editorCard}
                        cardId={editorCard}
                        onBusyChange={setBusy}
                        onClose={() => {
                            if (!busyRef.current) setEditorCard(null);
                        }}
                        onSaved={() => {
                            setEditorCard(null);
                            void directory.retry();
                        }}
                    />
                )}
            </fieldset>
        </section>
    );
}
