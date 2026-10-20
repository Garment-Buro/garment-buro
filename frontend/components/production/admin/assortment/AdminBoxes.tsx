'use client';

import { useRef, useState, type FormEvent } from 'react';
import { PiLink, PiPencilSimple, PiPlus } from 'react-icons/pi';
import {
    useBoxDirectory,
    usePackagingRules,
} from '@/hooks/production/useReferenceDirectory';
import { ReferencePicker } from './ReferencePicker';
import { saveAssortment } from '@/lib/api/productionAssortment';
import { compactDecimal } from '@/lib/production/numbers';
import type {
    PackagingBox,
    PackagingRule,
} from '@/lib/production/assortmentTypes';
import { AdminFilters } from '../AdminFilters';
import { AssortmentDialog, AssortmentFeedback } from './AssortmentDialog';
import styles from '../ProductionAdmin.module.css';

type BoxForm = Partial<PackagingBox> & {
    code: string;
    name: string;
    inner_length_cm: string;
    inner_width_cm: string;
    inner_height_cm: string;
    max_items: number;
    unit_cost: string;
    stock_quantity: number;
    minimum_stock_quantity: number;
    photo_media_object_id: number | null;
    is_active: boolean;
};
type RuleForm = Partial<PackagingRule> & {
    garment_model_id: number;
    box_id: number;
    max_items: number;
    priority: number;
    box_capacity?: number | null;
};

export function AdminBoxes() {
    const [search, setSearch] = useState('');
    const [activityFilter, setActivityFilter] = useState('');
    const [stockFilter, setStockFilter] = useState('');
    const [sorting, setSorting] = useState('name:asc');
    const [editor, setEditor] = useState<BoxForm | null>(null);
    const [ruleEditor, setRuleEditor] = useState<RuleForm | null>(null);
    const [saving, setSaving] = useState(false);
    const writeLocked = useRef(false);
    const [formError, setFormError] = useState('');
    const [ruleSearch, setRuleSearch] = useState('');
    const boxes = useBoxDirectory({
        query: search,
        active: activityFilter ? activityFilter === 'active' : undefined,
        stock: stockFilter || 'all',
        sort: sorting,
        limit: 24,
    });
    const rules = usePackagingRules({ query: ruleSearch, limit: 24 });
    const visibleBoxes = boxes.items;

    const submitBox = async (event: FormEvent) => {
        event.preventDefault();
        if (!editor || writeLocked.current) return;
        writeLocked.current = true;
        setSaving(true);
        setFormError('');
        try {
            await saveAssortment(
                editor.id ? `boxes/${editor.id}` : 'boxes',
                editor.id ? 'PUT' : 'POST',
                {
                    code: editor.code,
                    name: editor.name,
                    inner_length_cm: Number(editor.inner_length_cm),
                    inner_width_cm: Number(editor.inner_width_cm),
                    inner_height_cm: Number(editor.inner_height_cm),
                    max_items: Number(editor.max_items),
                    unit_cost: Number(editor.unit_cost || 0),
                    currency: 'RUB',
                    stock_quantity: Number(editor.stock_quantity),
                    minimum_stock_quantity: Number(
                        editor.minimum_stock_quantity,
                    ),
                    photo_media_object_id: editor.photo_media_object_id,
                    is_active: editor.is_active,
                    ...(editor.id ? { expected_version: editor.version } : {}),
                },
            );
            setEditor(null);
            boxes.retry();
        } catch (reason) {
            setFormError(
                reason instanceof Error
                    ? reason.message
                    : 'Не удалось сохранить коробку',
            );
        } finally {
            writeLocked.current = false;
            setSaving(false);
        }
    };
    const submitRule = async (event: FormEvent) => {
        event.preventDefault();
        if (!ruleEditor || writeLocked.current) return;
        writeLocked.current = true;
        setSaving(true);
        setFormError('');
        try {
            await saveAssortment(
                ruleEditor.id
                    ? `packaging-rules/${ruleEditor.id}`
                    : 'packaging-rules',
                ruleEditor.id ? 'PUT' : 'POST',
                {
                    garment_model_id: ruleEditor.garment_model_id,
                    box_id: ruleEditor.box_id,
                    max_items: Number(ruleEditor.max_items),
                    priority: Number(ruleEditor.priority),
                    ...(ruleEditor.id
                        ? { expected_version: ruleEditor.version }
                        : {}),
                },
            );
            setRuleEditor(null);
            rules.retry();
        } catch (reason) {
            setFormError(
                reason instanceof Error
                    ? reason.message
                    : 'Не удалось сохранить правило упаковки',
            );
        } finally {
            writeLocked.current = false;
            setSaving(false);
        }
    };

    return (
        <section aria-busy={boxes.loading}>
            <fieldset className={styles.adminFields} disabled={saving}>
                <div className={styles.assortmentHeading}>
                    <div>
                        <h3>Коробки</h3>
                        <p className={styles.muted}>
                            Габариты, вместимость, остатки и подбор упаковки для
                            моделей.
                        </p>
                    </div>
                    <div className={styles.headingActions}>
                        <button
                            onClick={() =>
                                setRuleEditor({
                                    garment_model_id: 0,
                                    box_id: 0,
                                    max_items: 1,
                                    priority: 0,
                                })
                            }
                        >
                            <PiLink aria-hidden /> Правило упаковки
                        </button>
                        <button
                            onClick={() => {
                                setEditor({
                                    code: '',
                                    name: '',
                                    inner_length_cm: '',
                                    inner_width_cm: '',
                                    inner_height_cm: '',
                                    max_items: 1,
                                    unit_cost: '0',
                                    stock_quantity: 0,
                                    minimum_stock_quantity: 0,
                                    photo_media_object_id: null,
                                    is_active: true,
                                });
                            }}
                        >
                            <PiPlus aria-hidden /> Добавить коробку
                        </button>
                    </div>
                </div>
                <div className={styles.assortmentFilters}>
                    <label className={styles.assortmentSearch}>
                        Поиск коробки
                        <input
                            type="search"
                            value={search}
                            placeholder="Название или код"
                            onChange={(event) => setSearch(event.target.value)}
                        />
                    </label>
                    <AdminFilters
                        groups={[
                            {
                                key: 'activity',
                                label: 'Видимость',
                                options: [
                                    ['', 'Все коробки'],
                                    ['active', 'Активные'],
                                    ['hidden', 'Скрытые'],
                                ],
                            },
                            {
                                key: 'stock',
                                label: 'Остаток',
                                options: [
                                    ['', 'Любой остаток'],
                                    ['available', 'Выше минимума'],
                                    ['low', 'Заканчивается'],
                                ],
                            },
                            {
                                key: 'sorting',
                                label: 'Сортировка',
                                options: [
                                    ['name:asc', 'Название: А–Я'],
                                    ['code:asc', 'По коду'],
                                    ['stock:asc', 'Сначала заканчивающиеся'],
                                    ['stock:desc', 'Сначала большие остатки'],
                                    ['capacity:desc', 'Сначала вместительные'],
                                    ['price:asc', 'Сначала дешевле'],
                                ],
                            },
                        ]}
                        values={{
                            activity: activityFilter,
                            stock: stockFilter,
                            sorting,
                        }}
                        defaults={{
                            activity: '',
                            stock: '',
                            sorting: 'name:asc',
                        }}
                        onApply={(values) => {
                            setActivityFilter(values.activity);
                            setStockFilter(values.stock);
                            setSorting(values.sorting);
                        }}
                    />
                </div>
                <AssortmentFeedback
                    loading={boxes.loading}
                    error={boxes.message}
                    empty={!boxes.loading && visibleBoxes.length === 0}
                />
                <div className={styles.assortmentCards}>
                    {visibleBoxes.map((box) => (
                        <article className={styles.assortmentCard} key={box.id}>
                            <div className={styles.assortmentCardTop}>
                                <div>
                                    <span className={styles.badge}>
                                        {box.code}
                                    </span>
                                    <h4>{box.name}</h4>
                                </div>
                                <button
                                    className={styles.iconButton}
                                    onClick={() => {
                                        setEditor({
                                            ...box,
                                            inner_length_cm: compactDecimal(
                                                box.inner_length_cm,
                                            ),
                                            inner_width_cm: compactDecimal(
                                                box.inner_width_cm,
                                            ),
                                            inner_height_cm: compactDecimal(
                                                box.inner_height_cm,
                                            ),
                                            unit_cost: compactDecimal(
                                                box.unit_cost,
                                            ),
                                        });
                                    }}
                                    aria-label={`Изменить коробку ${box.name}`}
                                >
                                    <PiPencilSimple aria-hidden />
                                </button>
                            </div>
                            <p>
                                {compactDecimal(box.inner_length_cm)} ×{' '}
                                {compactDecimal(box.inner_width_cm)} ×{' '}
                                {compactDecimal(box.inner_height_cm)} см
                            </p>
                            <dl className={styles.compactFacts}>
                                <div>
                                    <dt>Вместимость</dt>
                                    <dd>{box.max_items} шт.</dd>
                                </div>
                                <div>
                                    <dt>Остаток</dt>
                                    <dd>{box.stock_quantity}</dd>
                                </div>
                                <div>
                                    <dt>Цена</dt>
                                    <dd>{compactDecimal(box.unit_cost)} ₽</dd>
                                </div>
                            </dl>
                        </article>
                    ))}
                </div>
                {boxes.message && (
                    <button type="button" onClick={() => void boxes.retry()}>
                        Обновить коробки
                    </button>
                )}
                {boxes.hasMore && (
                    <button
                        type="button"
                        disabled={boxes.loadingMore}
                        onClick={() => void boxes.loadMore()}
                    >
                        Ещё коробки
                    </button>
                )}
                <section className={styles.relatedSection}>
                    <h4>Правила упаковки</h4>
                    <label>
                        Поиск правил упаковки
                        <input
                            type="search"
                            value={ruleSearch}
                            onChange={(event) =>
                                setRuleSearch(event.target.value)
                            }
                        />
                    </label>
                    <AssortmentFeedback
                        loading={rules.loading}
                        error={rules.message}
                        empty={!rules.loading && !rules.items.length}
                    />
                    {rules.message && (
                        <button
                            type="button"
                            onClick={() => void rules.retry()}
                        >
                            Обновить правила упаковки
                        </button>
                    )}
                    <div className={styles.relationshipList}>
                        {rules.items.map((rule) => (
                            <button
                                key={rule.id}
                                className={styles.relationshipCard}
                                onClick={() => setRuleEditor({ ...rule })}
                            >
                                <span>
                                    <strong>{rule.garment_model_name}</strong>
                                    <small>{rule.box_name}</small>
                                </span>
                                <span>
                                    до {rule.max_items} шт. · очередь{' '}
                                    {rule.priority + 1}
                                </span>
                            </button>
                        ))}
                    </div>
                    {rules.hasMore && (
                        <button
                            type="button"
                            disabled={rules.loadingMore}
                            onClick={() => void rules.loadMore()}
                        >
                            Ещё правила упаковки
                        </button>
                    )}
                </section>
                {editor && (
                    <AssortmentDialog
                        title={editor.id ? 'Изменить коробку' : 'Новая коробка'}
                        onClose={() => setEditor(null)}
                    >
                        <form onSubmit={submitBox}>
                            <div className={styles.formGrid}>
                                <label>
                                    Название
                                    <input
                                        required
                                        value={editor.name}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                name: event.target.value,
                                            })
                                        }
                                    />
                                </label>
                                <label>
                                    Код
                                    <input
                                        required
                                        value={editor.code}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                code: event.target.value.toUpperCase(),
                                            })
                                        }
                                    />
                                </label>
                                {(
                                    [
                                        ['inner_length_cm', 'Длина внутри, см'],
                                        ['inner_width_cm', 'Ширина внутри, см'],
                                        [
                                            'inner_height_cm',
                                            'Высота внутри, см',
                                        ],
                                    ] as const
                                ).map(([field, label]) => (
                                    <label key={field}>
                                        {label}
                                        <input
                                            required
                                            type="number"
                                            min="0.01"
                                            step="0.01"
                                            value={editor[field]}
                                            onChange={(event) =>
                                                setEditor({
                                                    ...editor,
                                                    [field]: event.target.value,
                                                })
                                            }
                                        />
                                    </label>
                                ))}
                                <label>
                                    Вместимость, шт.
                                    <input
                                        required
                                        type="number"
                                        min="1"
                                        value={editor.max_items}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                max_items: Number(
                                                    event.target.value,
                                                ),
                                            })
                                        }
                                    />
                                </label>
                                <label>
                                    Цена
                                    <input
                                        type="number"
                                        min="0"
                                        step="0.01"
                                        value={editor.unit_cost}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                unit_cost: event.target.value,
                                            })
                                        }
                                    />
                                </label>
                                <label>
                                    Остаток
                                    <input
                                        type="number"
                                        min="0"
                                        value={editor.stock_quantity}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                stock_quantity: Number(
                                                    event.target.value,
                                                ),
                                            })
                                        }
                                    />
                                </label>
                                <label>
                                    Минимальный остаток
                                    <input
                                        type="number"
                                        min="0"
                                        value={editor.minimum_stock_quantity}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                minimum_stock_quantity: Number(
                                                    event.target.value,
                                                ),
                                            })
                                        }
                                    />
                                </label>
                                <label className={styles.checkField}>
                                    <input
                                        type="checkbox"
                                        checked={editor.is_active}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                is_active: event.target.checked,
                                            })
                                        }
                                    />
                                    Коробка доступна
                                </label>
                            </div>
                            {formError && (
                                <p className={styles.error}>{formError}</p>
                            )}
                            <div className={styles.editorActions}>
                                <button
                                    type="button"
                                    onClick={() => setEditor(null)}
                                >
                                    Отмена
                                </button>
                                <button
                                    className={styles.primaryButton}
                                    disabled={saving}
                                >
                                    Сохранить
                                </button>
                            </div>
                        </form>
                    </AssortmentDialog>
                )}
                {ruleEditor && (
                    <AssortmentDialog
                        title="Правило упаковки"
                        description="Укажите, сколько изделий выбранной модели помещается в конкретную коробку. Если коробок несколько, меньшее число означает более высокий приоритет."
                        onClose={() => setRuleEditor(null)}
                    >
                        <form onSubmit={submitRule}>
                            <div className={styles.packagingRuleGuide}>
                                <span>Модель</span>
                                <strong aria-hidden>→</strong>
                                <span>Коробка</span>
                                <strong aria-hidden>→</strong>
                                <span>Количество</span>
                            </div>
                            <div className={styles.formGrid}>
                                <ReferencePicker
                                    kind="models"
                                    value={ruleEditor.garment_model_id}
                                    onChange={(garment_model_id) =>
                                        setRuleEditor({
                                            ...ruleEditor,
                                            garment_model_id,
                                        })
                                    }
                                />
                                <ReferencePicker
                                    kind="boxes"
                                    value={ruleEditor.box_id}
                                    onChange={(box_id, row) =>
                                        setRuleEditor({
                                            ...ruleEditor,
                                            box_id,
                                            box_capacity:
                                                row?.max_items ?? null,
                                            max_items: row?.max_items
                                                ? Math.min(
                                                      ruleEditor.max_items,
                                                      row.max_items,
                                                  )
                                                : ruleEditor.max_items,
                                        })
                                    }
                                />
                                <label>
                                    Максимум изделий этой модели
                                    <input
                                        required
                                        type="number"
                                        min="1"
                                        max={
                                            ruleEditor.box_capacity ?? undefined
                                        }
                                        value={ruleEditor.max_items}
                                        onChange={(event) =>
                                            setRuleEditor({
                                                ...ruleEditor,
                                                max_items: Number(
                                                    event.target.value,
                                                ),
                                            })
                                        }
                                    />
                                </label>
                                <label>
                                    Очередь выбора
                                    <input
                                        type="number"
                                        min="0"
                                        value={ruleEditor.priority}
                                        onChange={(event) =>
                                            setRuleEditor({
                                                ...ruleEditor,
                                                priority: Number(
                                                    event.target.value,
                                                ),
                                            })
                                        }
                                    />
                                    <small>
                                        0 — основная коробка, 1 и далее —
                                        запасные.
                                    </small>
                                </label>
                            </div>
                            {formError && (
                                <p className={styles.error}>{formError}</p>
                            )}
                            <div className={styles.editorActions}>
                                <button
                                    type="button"
                                    onClick={() => setRuleEditor(null)}
                                >
                                    Отмена
                                </button>
                                <button
                                    className={styles.primaryButton}
                                    disabled={saving}
                                >
                                    Сохранить правило
                                </button>
                            </div>
                        </form>
                    </AssortmentDialog>
                )}
            </fieldset>
        </section>
    );
}
