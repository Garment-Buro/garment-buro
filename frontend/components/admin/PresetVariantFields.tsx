import { useState } from 'react';
import { useEditorOptions } from '@/hooks/admin/useEditorOptions';
import { productionEditorClient } from '@/hooks/admin/catalogEditorClients';
import type { EditorModel, EditorFabric } from '@/lib/products/editorClient';
import type { PresetEditor } from '@/lib/production/presetEditor';
import { setPresetField, type PresetFieldsProps } from './presetFields';
import styles from '@/components/production/admin/ProductionAdmin.module.css';
import {
    rebuildPresetVariants,
    PRESET_VARIANT_LIMIT,
} from '@/lib/production/presetEditor';
import { ProductVariantEditor } from './ProductVariantEditor';

export function PresetVariantFields({
    editor,
    setEditor,
    disabled,
    model,
    selectedFabrics,
    referencesLoading,
    referenceError,
    upload,
}: PresetFieldsProps & {
    model: EditorModel | undefined;
    selectedFabrics: EditorFabric[];
    referencesLoading: boolean;
    referenceError: string;
    upload: (files: File[]) => Promise<string[]>;
}) {
    const [matrixError, setMatrixError] = useState('');
    const [fabricSearch, setFabricSearch] = useState('');
    const [sizeSearch, setSizeSearch] = useState('');
    const sizePage = useEditorOptions(
        {
            query: sizeSearch,
            model_id: editor.garment_model_id ?? undefined,
            limit: 24,
        },
        productionEditorClient.sizes,
        Boolean(editor.garment_model_id),
    );
    const fabrics = useEditorOptions(
        {
            query: fabricSearch,
            model_id: editor.garment_model_id ?? undefined,
            limit: 24,
        },
        productionEditorClient.fabrics,
        Boolean(editor.garment_model_id),
    );
    const set = <K extends keyof PresetEditor>(
        key: K,
        value: PresetEditor[K],
    ) => setPresetField(setEditor, key, value);
    const sizes = [
        ...new Set(
            editor?.variants.flatMap((row) =>
                row.garment_size_id === null ? [] : [row.garment_size_id],
            ) ?? [],
        ),
    ];
    const fabricIds = [
        ...new Set(
            editor?.variants.flatMap((row) =>
                row.fabric_id === null ? [] : [row.fabric_id],
            ) ?? [],
        ),
    ];
    const materialOptions = [
        ...new Map(
            [...selectedFabrics, ...fabrics.items].map((row) => [row.id, row]),
        ).values(),
    ];
    const sizeOptions = [
        ...new Map(
            [...(model?.sizes ?? []), ...sizePage.items].map((row) => [
                row.id,
                row,
            ]),
        ).values(),
    ];
    const matrix = (nextSizes: number[], nextFabrics: number[]) => {
        if (!editor || !model || referencesLoading || referenceError) return;
        try {
            const variants = rebuildPresetVariants(
                editor.variants,
                { ...model, sizes: sizeOptions },
                materialOptions,
                nextSizes,
                nextFabrics,
            );
            set('variants', variants);
            setMatrixError('');
        } catch (reason) {
            setMatrixError(
                reason instanceof Error
                    ? reason.message
                    : 'Не удалось построить варианты.',
            );
        }
    };
    return (
        <fieldset
            className={styles.formSection}
            disabled={disabled || referencesLoading}
        >
            <legend>Варианты</legend>
            {matrixError && <p role="alert">{matrixError}</p>}
            {model && (
                <>
                    <h4>Размеры</h4>
                    <label>
                        Поиск размера
                        <input
                            type="search"
                            value={sizeSearch}
                            onChange={(event) =>
                                setSizeSearch(event.target.value)
                            }
                        />
                    </label>
                    <div className={styles.variantChoiceGrid}>
                        {sizeOptions
                            .filter(
                                (row) =>
                                    row.is_active || sizes.includes(row.id),
                            )
                            .map((row) => (
                                <button
                                    key={row.id}
                                    type="button"
                                    aria-pressed={sizes.includes(row.id)}
                                    onClick={() =>
                                        matrix(
                                            sizes.includes(row.id)
                                                ? sizes.filter(
                                                      (value) =>
                                                          value !== row.id,
                                                  )
                                                : [...sizes, row.id],
                                            fabricIds,
                                        )
                                    }
                                >
                                    {row.code}
                                    {row.is_active ? '' : ' · архив'}
                                </button>
                            ))}
                    </div>
                    {sizePage.message && (
                        <p role="alert">
                            {sizePage.message}
                            <button
                                type="button"
                                onClick={() => void sizePage.retry()}
                            >
                                Повторить поиск размеров
                            </button>
                        </p>
                    )}
                    {sizePage.hasMore && (
                        <button
                            type="button"
                            disabled={sizePage.loadingMore}
                            onClick={() => void sizePage.loadMore()}
                        >
                            Ещё размеры
                        </button>
                    )}
                    <label>
                        Поиск ткани
                        <input
                            type="search"
                            value={fabricSearch}
                            onChange={(event) =>
                                setFabricSearch(event.target.value)
                            }
                        />
                    </label>
                    <div className={styles.variantChoiceGrid}>
                        {materialOptions.map((row) => (
                            <button
                                key={row.id}
                                type="button"
                                aria-pressed={fabricIds.includes(row.id)}
                                onClick={() =>
                                    matrix(
                                        sizes,
                                        fabricIds.includes(row.id)
                                            ? fabricIds.filter(
                                                  (value) => value !== row.id,
                                              )
                                            : [...fabricIds, row.id],
                                    )
                                }
                            >
                                {row.color_name} · {row.name}
                                {row.is_active ? '' : ' · архив'}
                            </button>
                        ))}
                    </div>
                    {fabrics.message && (
                        <p role="alert">
                            {fabrics.message}
                            <button
                                type="button"
                                onClick={() => void fabrics.retry()}
                            >
                                Повторить поиск тканей
                            </button>
                        </p>
                    )}
                    {fabrics.hasMore && (
                        <button
                            type="button"
                            disabled={fabrics.loadingMore}
                            onClick={() => void fabrics.loadMore()}
                        >
                            Ещё ткани
                        </button>
                    )}
                </>
            )}
            {editor.variants.map((variant, index) => (
                <ProductVariantEditor
                    key={
                        variant.id ||
                        `${variant.garment_size_id}-${variant.fabric_id}-${index}`
                    }
                    variant={variant}
                    linked={editor.garment_model_id !== null}
                    disabled={disabled}
                    upload={upload}
                    onChange={(value) =>
                        setEditor((current) =>
                            current
                                ? {
                                      ...current,
                                      variants: current.variants.map(
                                          (row, i) =>
                                              i === index
                                                  ? {
                                                        ...row,
                                                        ...value,
                                                    }
                                                  : row,
                                      ),
                                  }
                                : current,
                        )
                    }
                    onRemove={() =>
                        set(
                            'variants',
                            editor.variants.filter((_, i) => i !== index),
                        )
                    }
                />
            ))}
            {editor.garment_model_id === null && (
                <button
                    type="button"
                    disabled={editor.variants.length >= PRESET_VARIANT_LIMIT}
                    onClick={() =>
                        set('variants', [
                            ...editor.variants,
                            {
                                id: 0,
                                sku: null,
                                garment_size_id: null,
                                fabric_id: null,
                                size: null,
                                color: null,
                                color_hex: '#000000',
                                stock_quantity: 0,
                                reserved_quantity: 0,
                                available_stock_quantity: 0,
                                width_cm: null,
                                height_cm: null,
                                preview_image: null,
                                images: null,
                            },
                        ])
                    }
                >
                    Добавить вариант
                </button>
            )}
        </fieldset>
    );
}
