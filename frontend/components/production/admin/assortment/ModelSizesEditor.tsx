import type { Dispatch, SetStateAction } from 'react';
import type { ModelEditor } from '@/lib/production/modelEditor';
import styles from '../ProductionAdmin.module.css';
import { useState } from 'react';
import {
    PiArrowRight,
    PiCheck,
    PiPlus,
    PiRuler,
    PiTrash,
} from 'react-icons/pi';
import type { GarmentSize } from '@/lib/production/assortmentTypes';
import { emptySize, MODEL_SIZE_LIMIT } from '@/lib/production/modelEditor';
type SizeRangeField =
    | 'min_width_cm'
    | 'max_width_cm'
    | 'min_length_cm'
    | 'max_length_cm'
    | 'min_height_cm'
    | 'max_height_cm';
function SizeRangeEditor({
    label,
    size,
    minimum,
    maximum,
    onChange,
}: {
    label: string;
    size: GarmentSize;
    minimum: SizeRangeField;
    maximum: SizeRangeField;
    onChange: (field: SizeRangeField, value: string) => void;
}) {
    return (
        <section className={styles.sizeRangeCard}>
            <div className={styles.sizeRangeHeading}>
                <PiRuler aria-hidden />
                <strong>{label}</strong>
            </div>
            <div className={styles.sizeRangeInputs}>
                <label>
                    <span>От</span>
                    <input
                        type="number"
                        min="0.01"
                        step="0.01"
                        inputMode="decimal"
                        value={size[minimum] ?? ''}
                        placeholder="—"
                        onChange={(event) =>
                            onChange(minimum, event.target.value)
                        }
                    />
                </label>
                <PiArrowRight aria-hidden />
                <label>
                    <span>До</span>
                    <input
                        type="number"
                        min="0.01"
                        step="0.01"
                        inputMode="decimal"
                        value={size[maximum] ?? ''}
                        placeholder="—"
                        onChange={(event) =>
                            onChange(maximum, event.target.value)
                        }
                    />
                </label>
                <span className={styles.sizeRangeUnit}>см</span>
            </div>
        </section>
    );
}
const sizeSummary = (size: GarmentSize) => {
    const base =
        size.base_width_cm && size.base_length_cm
            ? `База ${Number(size.base_width_cm)} × ${Number(size.base_length_cm)} см`
            : 'База не задана';
    const width =
        size.min_width_cm && size.max_width_cm
            ? `${Number(size.min_width_cm)}–${Number(size.max_width_cm)} см`
            : 'Ширина не задана';
    const length =
        size.min_length_cm && size.max_length_cm
            ? `${Number(size.min_length_cm)}–${Number(size.max_length_cm)} см`
            : 'Длина не задана';
    return `${base} · ${width} · ${length}`;
};
export function ModelSizesEditor({
    editor,
    setEditor,
}: {
    editor: ModelEditor;
    setEditor: Dispatch<SetStateAction<ModelEditor | null>>;
}) {
    const [activeSizeIndex, setActiveSizeIndex] = useState(0);
    const activeSize = editor.sizes[activeSizeIndex] ?? null;
    const updateSize = (
        index: number,
        field: keyof GarmentSize,
        value: string,
    ) => {
        setEditor((current) => {
            if (!current) return current;
            const sizes = [...current.sizes];
            sizes[index] = {
                ...sizes[index],
                [field]: field === 'sort_order' ? Number(value) : value || null,
            };
            return { ...current, sizes };
        });
    };
    return (
        <fieldset className={styles.formSection}>
            <legend>Размерная сетка</legend>
            <div
                className={styles.sizeCardList}
                role="tablist"
                aria-label="Размеры модели"
            >
                {editor.sizes.map((size, index) => (
                    <button
                        type="button"
                        role="tab"
                        aria-selected={activeSizeIndex === index}
                        className={styles.sizeCard}
                        data-selected={activeSizeIndex === index}
                        key={size.id ?? `new-${index}`}
                        onClick={() => setActiveSizeIndex(index)}
                    >
                        <strong>{size.code || `Размер ${index + 1}`}</strong>
                        <small>{sizeSummary(size)}</small>
                    </button>
                ))}
                <button
                    type="button"
                    className={styles.sizeCardAdd}
                    disabled={editor.sizes.length >= MODEL_SIZE_LIMIT}
                    onClick={() => {
                        const nextIndex = editor.sizes.length;
                        if (nextIndex >= MODEL_SIZE_LIMIT) return;
                        setEditor((current) =>
                            !current || current.sizes.length >= MODEL_SIZE_LIMIT
                                ? current
                                : {
                                      ...current,
                                      sizes: [
                                          ...current.sizes,
                                          emptySize(current.sizes.length),
                                      ],
                                  },
                        );
                        setActiveSizeIndex(nextIndex);
                    }}
                >
                    <PiPlus aria-hidden />
                    <span>Добавить размер</span>
                </button>
            </div>
            {activeSize && (
                <article className={styles.sizeDetailCard}>
                    <div className={styles.sizeDetailHeading}>
                        <div>
                            <h4>
                                {activeSize.code ||
                                    `Размер ${activeSizeIndex + 1}`}
                            </h4>
                            <small>Укажите границы, доступные покупателю</small>
                        </div>
                        <button
                            type="button"
                            className={styles.iconButton}
                            disabled={editor.sizes.length === 1}
                            onClick={() => {
                                const sizes = editor.sizes.filter(
                                    (_, index) => index !== activeSizeIndex,
                                );
                                const removedCode =
                                    editor.sizes[activeSizeIndex]?.code;
                                setEditor({
                                    ...editor,
                                    sizes,
                                    base_size_code:
                                        editor.base_size_code === removedCode
                                            ? sizes[0]?.code || null
                                            : editor.base_size_code,
                                });
                                setActiveSizeIndex((current) =>
                                    Math.max(
                                        0,
                                        Math.min(current, sizes.length - 1),
                                    ),
                                );
                            }}
                            aria-label={`Удалить размер ${activeSize.code || activeSizeIndex + 1}`}
                        >
                            <PiTrash aria-hidden />
                        </button>
                    </div>
                    <div className={styles.sizePrimaryFields}>
                        <label>
                            Код размера
                            <input
                                required
                                value={activeSize.code}
                                placeholder="M"
                                onChange={(event) => {
                                    const nextCode =
                                        event.target.value.toUpperCase();
                                    setEditor((current) => {
                                        if (!current) return current;
                                        const sizes = [...current.sizes];
                                        const previousCode =
                                            sizes[activeSizeIndex].code;
                                        sizes[activeSizeIndex] = {
                                            ...sizes[activeSizeIndex],
                                            code: nextCode,
                                        };
                                        return {
                                            ...current,
                                            sizes,
                                            base_size_code:
                                                !current.base_size_code ||
                                                current.base_size_code ===
                                                    previousCode
                                                    ? nextCode || null
                                                    : current.base_size_code,
                                        };
                                    });
                                }}
                            />
                        </label>
                        <label>
                            Базовая цена
                            <input
                                type="number"
                                min="0"
                                step="0.01"
                                value={activeSize.base_price}
                                onChange={(event) =>
                                    updateSize(
                                        activeSizeIndex,
                                        'base_price',
                                        event.target.value,
                                    )
                                }
                            />
                        </label>
                        <label>
                            Базовая ширина, см
                            <input
                                required
                                type="number"
                                min="0.01"
                                step="0.01"
                                inputMode="decimal"
                                value={activeSize.base_width_cm ?? ''}
                                placeholder="60"
                                onChange={(event) =>
                                    updateSize(
                                        activeSizeIndex,
                                        'base_width_cm',
                                        event.target.value,
                                    )
                                }
                            />
                        </label>
                        <label>
                            Базовая длина, см
                            <input
                                required
                                type="number"
                                min="0.01"
                                step="0.01"
                                inputMode="decimal"
                                value={activeSize.base_length_cm ?? ''}
                                placeholder="72"
                                onChange={(event) =>
                                    updateSize(
                                        activeSizeIndex,
                                        'base_length_cm',
                                        event.target.value,
                                    )
                                }
                            />
                        </label>
                    </div>
                    <div className={styles.sizeRangeGrid}>
                        <SizeRangeEditor
                            label="Ширина изделия"
                            size={activeSize}
                            minimum="min_width_cm"
                            maximum="max_width_cm"
                            onChange={(field, value) =>
                                updateSize(activeSizeIndex, field, value)
                            }
                        />
                        <section className={styles.sizeRangeCard}>
                            <div className={styles.sizeRangeHeading}>
                                <PiRuler aria-hidden />
                                <strong>Длина по росту</strong>
                            </div>
                            <div className={styles.lengthHeightRows}>
                                {(
                                    [
                                        [
                                            'min_length_cm',
                                            'min_height_cm',
                                            'Минимум',
                                        ],
                                        [
                                            'max_length_cm',
                                            'max_height_cm',
                                            'Максимум',
                                        ],
                                    ] as const
                                ).map(([lengthField, heightField, label]) => (
                                    <div key={lengthField}>
                                        <small>{label}</small>
                                        <label>
                                            Длина
                                            <span>
                                                <input
                                                    type="number"
                                                    min="0.01"
                                                    step="0.01"
                                                    value={
                                                        activeSize[
                                                            lengthField
                                                        ] ?? ''
                                                    }
                                                    onChange={(event) =>
                                                        updateSize(
                                                            activeSizeIndex,
                                                            lengthField,
                                                            event.target.value,
                                                        )
                                                    }
                                                />
                                                см
                                            </span>
                                        </label>
                                        <PiArrowRight aria-hidden />
                                        <label>
                                            Рост человека
                                            <span>
                                                <input
                                                    type="number"
                                                    min="1"
                                                    step="1"
                                                    value={
                                                        activeSize[
                                                            heightField
                                                        ] ?? ''
                                                    }
                                                    onChange={(event) =>
                                                        updateSize(
                                                            activeSizeIndex,
                                                            heightField,
                                                            event.target.value,
                                                        )
                                                    }
                                                />
                                                см
                                            </span>
                                        </label>
                                    </div>
                                ))}
                            </div>
                        </section>
                        <section className={styles.sizeRangeCard}>
                            <div className={styles.sizeRangeHeading}>
                                <PiRuler aria-hidden />
                                <strong>Варианты рукава</strong>
                            </div>
                            <div className={styles.squareChoiceGrid}>
                                {(
                                    [
                                        [
                                            'allow_standard_sleeve',
                                            'Стандартный',
                                            'По лекалу',
                                        ],
                                        [
                                            'allow_height_sleeve',
                                            'Под рост',
                                            'По росту человека',
                                        ],
                                    ] as const
                                ).map(([field, label, hint]) => {
                                    const selected = activeSize[field];
                                    const otherSelected =
                                        field === 'allow_standard_sleeve'
                                            ? activeSize.allow_height_sleeve
                                            : activeSize.allow_standard_sleeve;
                                    return (
                                        <button
                                            type="button"
                                            key={field}
                                            data-selected={selected}
                                            aria-pressed={selected}
                                            disabled={
                                                selected && !otherSelected
                                            }
                                            onClick={() =>
                                                setEditor((current) => {
                                                    if (!current)
                                                        return current;
                                                    const sizes = [
                                                        ...current.sizes,
                                                    ];
                                                    sizes[activeSizeIndex] = {
                                                        ...sizes[
                                                            activeSizeIndex
                                                        ],
                                                        [field]: !selected,
                                                    };
                                                    return {
                                                        ...current,
                                                        sizes,
                                                    };
                                                })
                                            }
                                        >
                                            <PiCheck aria-hidden />
                                            <strong>{label}</strong>
                                            <small>{hint}</small>
                                        </button>
                                    );
                                })}
                            </div>
                        </section>
                    </div>
                </article>
            )}
        </fieldset>
    );
}
