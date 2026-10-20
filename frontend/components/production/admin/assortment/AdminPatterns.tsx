'use client';

import { useRef, useState } from 'react';
import { PiCaretDown, PiPlus } from 'react-icons/pi';
import { usePatternModels } from '@/hooks/production/useReferenceDirectory';
import type { PatternModelCard } from '@/lib/production/patternDirectory';
import { AdminFilters } from '../AdminFilters';
import { AssortmentFeedback } from './AssortmentDialog';
import { ReferencePicker } from './ReferencePicker';
import { PatternCoveragePanel } from './PatternCoveragePanel';
import { PatternEditor, type PatternTarget } from './PatternEditor';
import styles from '../ProductionAdmin.module.css';

export function AdminPatterns() {
    const [query, setQuery] = useState(''),
        [activityFilter, setActivityFilter] = useState(''),
        [sorting, setSorting] = useState('model:asc');
    const [modelFilter, setModelFilter] = useState<{
            id: number;
            name: string;
        } | null>(null),
        [chooseFilter, setChooseFilter] = useState(false);
    const [target, setTarget] = useState<PatternTarget | null>(null),
        [busy, setBusyState] = useState(false),
        [revision, setRevision] = useState(0);
    const locked = useRef(false);
    const directory = usePatternModels({
        query,
        model_id: modelFilter?.id,
        pattern_active: activityFilter
            ? activityFilter === 'active'
            : undefined,
        sort: sorting,
        limit: 24,
    });
    const setBusy = (value: boolean) => {
        locked.current = value;
        setBusyState(value);
    };
    return (
        <section aria-busy={directory.loading}>
            <fieldset className={styles.adminFields} disabled={busy}>
                <div className={styles.assortmentHeading}>
                    <div>
                        <h3>Лекала по моделям</h3>
                        <p className={styles.muted}>
                            Откройте модель, чтобы посмотреть участок сетки или
                            все сохранённые файлы.
                        </p>
                    </div>
                    <button type="button" onClick={() => setTarget({})}>
                        <PiPlus aria-hidden /> Добавить лекало
                    </button>
                </div>
                <div
                    className={`${styles.assortmentFilters} ${styles.patternFilters}`}
                >
                    <label className={styles.assortmentSearch}>
                        Поиск по модели или коду лекала
                        <input
                            type="search"
                            value={query}
                            placeholder="Модель или PAT-HOODIE-M"
                            onChange={(event) => setQuery(event.target.value)}
                        />
                    </label>
                    <button
                        type="button"
                        aria-expanded={chooseFilter}
                        onClick={() => setChooseFilter((value) => !value)}
                    >
                        {modelFilter
                            ? `Модель: ${modelFilter.name}`
                            : 'Выбрать модель'}
                    </button>
                    <AdminFilters
                        groups={[
                            {
                                key: 'activity',
                                label: 'Лекала',
                                options: [
                                    ['', 'Все состояния'],
                                    ['active', 'Есть активные'],
                                    ['hidden', 'Есть скрытые'],
                                ],
                            },
                            {
                                key: 'sorting',
                                label: 'Сортировка',
                                options: [
                                    ['model:asc', 'Модель: А–Я'],
                                    ['model:desc', 'Модель: Я–А'],
                                    ['code:asc', 'Код: А–Я'],
                                    ['code:desc', 'Код: Я–А'],
                                ],
                            },
                        ]}
                        values={{ activity: activityFilter, sorting }}
                        defaults={{ activity: '', sorting: 'model:asc' }}
                        onApply={(values) => {
                            setActivityFilter(values.activity);
                            setSorting(values.sorting);
                        }}
                    />
                </div>
                {chooseFilter && (
                    <div>
                        <ReferencePicker
                            kind="models"
                            value={modelFilter?.id ?? 0}
                            searchLabel="Найти модель для списка лекал"
                            moreLabel="Ещё модели для фильтра лекал"
                            onChange={(id, row) => {
                                if (id) {
                                    setModelFilter({
                                        id,
                                        name: row?.name ?? `№${id}`,
                                    });
                                    setChooseFilter(false);
                                }
                            }}
                        />
                        <button
                            type="button"
                            onClick={() => {
                                setModelFilter(null);
                                setChooseFilter(false);
                            }}
                        >
                            Все модели
                        </button>
                    </div>
                )}
                {modelFilter && !chooseFilter && (
                    <button type="button" onClick={() => setModelFilter(null)}>
                        Сбросить выбранную модель
                    </button>
                )}
                <AssortmentFeedback
                    loading={directory.loading}
                    error={directory.message}
                    empty={!directory.loading && !directory.items.length}
                />
                <div className={styles.patternCoverageList}>
                    {directory.items.map((model) => (
                        <PatternModel
                            key={model.id}
                            model={model}
                            revision={revision}
                            onOpen={setTarget}
                        />
                    ))}
                </div>
                {directory.message && (
                    <button
                        type="button"
                        onClick={() => void directory.retry()}
                    >
                        Обновить модели лекал
                    </button>
                )}
                {directory.hasMore && (
                    <button
                        type="button"
                        disabled={directory.loadingMore}
                        onClick={() => void directory.loadMore()}
                    >
                        Ещё модели для лекал
                    </button>
                )}
                {target && (
                    <PatternEditor
                        key={JSON.stringify(target)}
                        target={target}
                        onBusyChange={setBusy}
                        onClose={() => {
                            if (!locked.current) setTarget(null);
                        }}
                        onSaved={() => {
                            setTarget(null);
                            setRevision((value) => value + 1);
                            void directory.retry();
                        }}
                    />
                )}
            </fieldset>
        </section>
    );
}

function PatternModel({
    model,
    revision,
    onOpen,
}: {
    model: PatternModelCard;
    revision: number;
    onOpen: (target: PatternTarget) => void;
}) {
    const [open, setOpen] = useState(false);
    return (
        <details
            className={styles.patternModelCoverage}
            data-pattern-model={model.id}
            onToggle={(event) => setOpen(event.currentTarget.open)}
        >
            <summary>
                <div>
                    <strong>{model.name}</strong>
                    <small>{model.code}</small>
                </div>
                <div className={styles.patternCoverageMeta}>
                    <span
                        data-complete={
                            BigInt(model.required_count) > BigInt(0) &&
                            BigInt(model.uploaded_count) ===
                                BigInt(model.required_count)
                        }
                    >
                        {model.uploaded_count} из{' '}
                        {BigInt(model.required_count).toLocaleString('ru-RU')}
                    </span>
                    <small>
                        по активным размерам · всего файлов:{' '}
                        {model.pattern_count}
                    </small>
                    <PiCaretDown aria-hidden />
                </div>
            </summary>
            {open && (
                <PatternCoveragePanel
                    model={model}
                    revision={revision}
                    onOpen={onOpen}
                />
            )}
        </details>
    );
}
