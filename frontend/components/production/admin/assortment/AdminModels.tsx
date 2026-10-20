'use client';
import { useState } from 'react';
import { PiPencilSimple, PiPlus } from 'react-icons/pi';
import { useModelDirectory } from '@/hooks/production/useReferenceDirectory';
import { AdminFilters } from '../AdminFilters';
import { AssortmentFeedback } from './AssortmentDialog';
import { CategoryDirectory, CategoryFilter } from './CategoryDirectory';
import { CategoryEditor } from './CategoryEditor';
import { ModelEditorDialog } from './ModelEditorDialog';
import styles from '../ProductionAdmin.module.css';
export function AdminModels() {
    const [search, setSearch] = useState('');
    const [categoryFilter, setCategoryFilter] = useState<number | null>(null);
    const [activityFilter, setActivityFilter] = useState('');
    const [sorting, setSorting] = useState('name:asc');
    const [modelTarget, setModelTarget] = useState<number | null | undefined>();
    const [modelBusy, setModelBusy] = useState(false);
    const [categoryTarget, setCategoryTarget] = useState<
        number | null | undefined
    >();
    const [categoryBusy, setCategoryBusy] = useState(false),
        [categoryRevision, setCategoryRevision] = useState(0);
    const [categoryFilterName, setCategoryFilterName] = useState('');
    const directory = useModelDirectory({
        query: search,
        category_id: categoryFilter,
        active: activityFilter ? activityFilter === 'active' : undefined,
        sort: sorting,
        limit: 24,
    });
    const { items: models, loading, message: error, retry: reload } = directory;
    return (
        <section aria-busy={loading}>
            <fieldset
                className={styles.adminFields}
                disabled={categoryBusy || modelBusy}
            >
                <div className={styles.assortmentHeading}>
                    <div>
                        <h3>Модели изделий</h3>
                        <p className={styles.muted}>
                            Размеры, диапазоны мерок, вес и таблица размеров для
                            сайта.
                        </p>
                    </div>
                    <div className={styles.headingActions}>
                        <button onClick={() => setCategoryTarget(null)}>
                            <PiPlus aria-hidden /> Категория
                        </button>
                        <button onClick={() => setModelTarget(null)}>
                            <PiPlus aria-hidden /> Добавить модель
                        </button>
                    </div>
                </div>
                <CategoryDirectory
                    kind="model-categories"
                    onEdit={setCategoryTarget}
                    revision={categoryRevision}
                    selectedId={categoryFilter}
                    onSelect={(id, name) => {
                        setCategoryFilter((current) =>
                            current === id ? null : id,
                        );
                        setCategoryFilterName(name);
                    }}
                />
                <div className={styles.assortmentFilters}>
                    <label className={styles.assortmentSearch}>
                        Поиск модели
                        <input
                            value={search}
                            placeholder="Название или код"
                            onChange={(event) => setSearch(event.target.value)}
                        />
                    </label>
                    <CategoryFilter
                        revision={categoryRevision}
                        kind="model-categories"
                        value={categoryFilter ?? 0}
                        label={categoryFilterName}
                        onChange={(id, name) => {
                            setCategoryFilter(id || null);
                            setCategoryFilterName(name);
                        }}
                    />
                    <AdminFilters
                        groups={[
                            {
                                key: 'activity',
                                label: 'Видимость',
                                options: [
                                    ['', 'Все модели'],
                                    ['active', 'Активные'],
                                    ['hidden', 'Скрытые'],
                                ],
                            },
                            {
                                key: 'sorting',
                                label: 'Сортировка',
                                options: [
                                    ['name:asc', 'Название: А–Я'],
                                    ['name:desc', 'Название: Я–А'],
                                    ['code:asc', 'По коду'],
                                    ['sizes:desc', 'Больше размеров'],
                                    ['products:desc', 'Больше товаров'],
                                ],
                            },
                        ]}
                        values={{
                            activity: activityFilter,
                            sorting,
                        }}
                        defaults={{
                            activity: '',
                            sorting: 'name:asc',
                        }}
                        onApply={(values) => {
                            setActivityFilter(values.activity);
                            setSorting(values.sorting);
                        }}
                    />
                </div>
                <AssortmentFeedback
                    loading={loading}
                    error={error}
                    empty={!loading && models.length === 0}
                />
                {models.length > 0 && (
                    <div className={styles.assortmentCards}>
                        {models.map((model) => (
                            <article
                                className={styles.assortmentCard}
                                key={model.id}
                            >
                                <div className={styles.assortmentCardTop}>
                                    <div>
                                        <span className={styles.badge}>
                                            {model.category_name ??
                                                'Без категории'}
                                        </span>
                                        <h4>{model.name}</h4>
                                        <small>{model.code}</small>
                                    </div>
                                    <button
                                        className={styles.iconButton}
                                        onClick={() => setModelTarget(model.id)}
                                        aria-label={`Изменить модель ${model.name}`}
                                        title="Изменить"
                                    >
                                        <PiPencilSimple aria-hidden />
                                    </button>
                                </div>
                                <dl className={styles.compactFacts}>
                                    <div>
                                        <dt>Размеров</dt>
                                        <dd>{model.size_count}</dd>
                                    </div>
                                    <div>
                                        <dt>Товаров</dt>
                                        <dd>{model.product_count}</dd>
                                    </div>
                                    <div>
                                        <dt>Вес</dt>
                                        <dd>
                                            {model.base_weight_g
                                                ? `${model.base_weight_g} г`
                                                : 'Не задан'}
                                        </dd>
                                    </div>
                                </dl>
                                <p className={styles.muted}>
                                    {model.tech_card_name
                                        ? `Техкарта: ${model.tech_card_name}, версия ${model.tech_card_revision}`
                                        : 'Опубликованной техкарты нет'}
                                </p>
                            </article>
                        ))}
                    </div>
                )}
                {directory.message && (
                    <button
                        type="button"
                        onClick={() => void directory.retry()}
                    >
                        Обновить список моделей
                    </button>
                )}
                {directory.hasMore && (
                    <button
                        type="button"
                        className={styles.secondaryButton}
                        disabled={directory.loadingMore}
                        onClick={() => void directory.loadMore()}
                    >
                        Ещё модели изделий
                    </button>
                )}
                {modelTarget !== undefined && (
                    <ModelEditorDialog
                        key={String(modelTarget)}
                        id={modelTarget}
                        onBusyChange={setModelBusy}
                        onClose={() => setModelTarget(undefined)}
                        onSaved={() => {
                            setModelTarget(undefined);
                            void reload();
                        }}
                    />
                )}
                {categoryTarget !== undefined && (
                    <CategoryEditor
                        key={String(categoryTarget)}
                        kind="model-categories"
                        id={categoryTarget}
                        onBusyChange={setCategoryBusy}
                        onClose={() => setCategoryTarget(undefined)}
                        onSaved={() => {
                            setCategoryTarget(undefined);
                            setCategoryRevision((value) => value + 1);
                            void reload();
                        }}
                    />
                )}
            </fieldset>
        </section>
    );
}
