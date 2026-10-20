import type { ProductDetail } from '@/lib/production/assortmentTypes';
import { ProductEditorMedia } from './ProductEditorMedia';
import styles from '@/components/production/admin/ProductionAdmin.module.css';
type Variant = ProductDetail['variants'][number];
export function ProductVariantEditor({
    variant,
    onChange,
    onRemove,
    upload,
    linked,
    disabled,
}: {
    variant: Variant;
    onChange: (value: Partial<Variant>) => void;
    onRemove: () => void;
    upload: (files: File[]) => Promise<string[]>;
    linked: boolean;
    disabled: boolean;
}) {
    const patch = (value: Partial<Variant>) => onChange(value);
    return (
        <section
            className={styles.formSection}
            aria-label={`Вариант ${variant.size ?? 'без размера'} ${variant.color ?? ''}`}
        >
            <div className={styles.formGrid}>
                <label>
                    Размер
                    <input
                        value={variant.size ?? ''}
                        readOnly={linked}
                        onChange={(event) =>
                            patch({ size: event.target.value || null })
                        }
                    />
                </label>
                <label>
                    Цвет
                    <input
                        value={variant.color ?? ''}
                        readOnly={linked}
                        onChange={(event) =>
                            patch({ color: event.target.value || null })
                        }
                    />
                </label>
                {!linked && (
                    <label>
                        Код цвета
                        <input
                            type="color"
                            value={variant.color_hex ?? '#000000'}
                            onChange={(event) =>
                                patch({ color_hex: event.target.value })
                            }
                        />
                    </label>
                )}
                {linked ? (
                    <p className={styles.muted}>
                        Доступность рассчитывается по ткани модели.
                    </p>
                ) : (
                    <label>
                        Физический остаток
                        <input
                            type="number"
                            min="0"
                            step="1"
                            value={variant.stock_quantity}
                            onChange={(event) =>
                                patch({
                                    stock_quantity: Number(event.target.value),
                                })
                            }
                        />
                    </label>
                )}
                <label>
                    Ширина изделия, см
                    <input
                        type="number"
                        min="0"
                        step="0.1"
                        value={variant.width_cm ?? ''}
                        onChange={(event) =>
                            patch({
                                width_cm: event.target.value
                                    ? Number(event.target.value)
                                    : null,
                            })
                        }
                    />
                </label>
                <label>
                    Длина изделия, см
                    <input
                        type="number"
                        min="0"
                        step="0.1"
                        value={variant.height_cm ?? ''}
                        onChange={(event) =>
                            patch({
                                height_cm: event.target.value
                                    ? Number(event.target.value)
                                    : null,
                            })
                        }
                    />
                </label>
                <p className={styles.muted}>
                    Это размер изделия. Рост человека задаётся отдельно при
                    заказе.
                </p>
                {variant.sku && <p>Артикул: {variant.sku}</p>}
            </div>
            <ProductEditorMedia
                label="Фото варианта"
                value={variant.preview_image}
                upload={upload}
                disabled={disabled}
                onChange={(value) => patch({ preview_image: value })}
            />
            <ProductEditorMedia
                label="Дополнительные фото варианта"
                value={variant.images}
                multiple
                upload={upload}
                disabled={disabled}
                onChange={(value) => patch({ images: value })}
            />
            <button type="button" disabled={disabled} onClick={onRemove}>
                Убрать вариант
            </button>
        </section>
    );
}
