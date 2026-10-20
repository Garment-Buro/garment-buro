import { useState } from 'react';
import { useEditorOptions } from '@/hooks/admin/useEditorOptions';
import { productionEditorClient } from '@/hooks/admin/catalogEditorClients';
import type { EditorModel } from '@/lib/products/editorClient';
import type { PresetEditor } from '@/lib/production/presetEditor';
import { setPresetField, type PresetFieldsProps } from './presetFields';
import styles from '@/components/production/admin/ProductionAdmin.module.css';
import { ReferencePicker } from '@/components/production/admin/assortment/ReferencePicker';

export function PresetIdentityFields({
    editor,
    setEditor,
    disabled,
    model,
    requiredModel,
}: PresetFieldsProps & {
    model: EditorModel | undefined;
    requiredModel: boolean;
}) {
    const [modelSearch, setModelSearch] = useState('');
    const models = useEditorOptions(
        { query: modelSearch, limit: 24 },
        productionEditorClient.models,
    );
    const set = <K extends keyof PresetEditor>(
        key: K,
        value: PresetEditor[K],
    ) => setPresetField(setEditor, key, value);
    const modelOptions = [
        ...new Map(
            [
                ...(model
                    ? [model]
                    : editor.garment_model_id
                      ? [
                            {
                                id: editor.garment_model_id,
                                name: `Модель №${editor.garment_model_id}`,
                                is_active: true,
                            },
                        ]
                      : []),
                ...models.items,
            ].map((row) => [row.id, row]),
        ).values(),
    ];
    return (
        <fieldset className={styles.formSection} disabled={disabled}>
            <legend>Карточка пресета</legend>
            <div className={styles.formGrid}>
                <label className={styles.fullField}>
                    Название
                    <input
                        required
                        value={editor.title}
                        onChange={(event) => set('title', event.target.value)}
                    />
                </label>
                <label>
                    Slug
                    <input
                        pattern="[a-z0-9][a-z0-9-]*"
                        value={editor.slug ?? ''}
                        onChange={(event) =>
                            set('slug', event.target.value.toLowerCase())
                        }
                    />
                </label>
                <label>
                    Источник пресета
                    <select
                        aria-label="Источник пресета"
                        value={editor.preset_source}
                        onChange={(event) =>
                            set(
                                'preset_source',
                                event.target.value as 'garment_buro' | 'user',
                            )
                        }
                    >
                        <option value="garment_buro">Garment Buro</option>
                        <option value="user">Пресеты пользователей</option>
                    </select>
                </label>
                <label>
                    Теги
                    <input
                        value={editor.tagsText}
                        onChange={(event) =>
                            set('tagsText', event.target.value)
                        }
                    />
                </label>
                <ReferencePicker
                    kind="product-categories"
                    activeOnly
                    value={editor.category_id ?? 0}
                    required={false}
                    emptyLabel="Без категории"
                    onChange={(id) => set('category_id', id || null)}
                />
                <label>
                    Поиск модели
                    <input
                        type="search"
                        value={modelSearch}
                        onChange={(event) => setModelSearch(event.target.value)}
                    />
                </label>
                <label>
                    Производственная модель
                    <select
                        aria-label="Производственная модель"
                        required={requiredModel}
                        value={editor.garment_model_id ?? ''}
                        onChange={(event) =>
                            setEditor((current) =>
                                current
                                    ? {
                                          ...current,
                                          garment_model_id: event.target.value
                                              ? Number(event.target.value)
                                              : null,
                                          variants: [],
                                      }
                                    : current,
                            )
                        }
                    >
                        <option value="">Не назначена</option>
                        {modelOptions.map((row) => (
                            <option key={row.id} value={row.id}>
                                {row.name}
                                {row.is_active ? '' : ' · архив'}
                            </option>
                        ))}
                    </select>
                </label>
                {models.message && (
                    <p role="alert">
                        {models.message}
                        <button
                            type="button"
                            onClick={() => void models.retry()}
                        >
                            Повторить поиск моделей
                        </button>
                    </p>
                )}
                {models.hasMore && (
                    <button
                        type="button"
                        disabled={models.loadingMore}
                        onClick={() => void models.loadMore()}
                    >
                        Ещё модели
                    </button>
                )}
                <label>
                    Цена
                    <input
                        required
                        type="number"
                        min="0"
                        step="0.01"
                        value={editor.price}
                        onChange={(event) =>
                            set('price', Number(event.target.value))
                        }
                    />
                </label>
                <label>
                    Цена без скидки
                    <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={editor.old_price ?? ''}
                        onChange={(event) =>
                            set(
                                'old_price',
                                event.target.value
                                    ? Number(event.target.value)
                                    : null,
                            )
                        }
                    />
                </label>
                <label className={styles.fullField}>
                    Описание
                    <textarea
                        value={editor.description ?? ''}
                        onChange={(event) =>
                            set('description', event.target.value || null)
                        }
                    />
                </label>
                <label>
                    Состав
                    <input
                        value={editor.composition ?? ''}
                        onChange={(event) =>
                            set('composition', event.target.value || null)
                        }
                    />
                </label>
                <label>
                    Информация о модели
                    <input
                        value={editor.model_info ?? ''}
                        onChange={(event) =>
                            set('model_info', event.target.value || null)
                        }
                    />
                </label>
                <label className={styles.checkField}>
                    <input
                        type="checkbox"
                        checked={editor.is_active}
                        onChange={(event) =>
                            set('is_active', event.target.checked)
                        }
                    />
                    Товар активен
                </label>
                <label>
                    Вес, кг
                    <input
                        type="number"
                        min="0"
                        step="0.001"
                        value={editor.weight}
                        onChange={(event) =>
                            set('weight', Number(event.target.value))
                        }
                    />
                </label>
                {(['height', 'width', 'length'] as const).map((key, index) => (
                    <label key={key}>
                        {['Высота', 'Ширина', 'Длина'][index]} упаковки, см
                        <input
                            type="number"
                            min="0"
                            step="0.1"
                            value={editor[key]}
                            onChange={(event) =>
                                set(key, Number(event.target.value))
                            }
                        />
                    </label>
                ))}
                {editor.garment_model_id === null && (
                    <label>
                        Физический остаток товара
                        <input
                            type="number"
                            min="0"
                            step="1"
                            value={editor.stock_quantity}
                            onChange={(event) =>
                                set(
                                    'stock_quantity',
                                    Number(event.target.value),
                                )
                            }
                        />
                    </label>
                )}
            </div>
        </fieldset>
    );
}
