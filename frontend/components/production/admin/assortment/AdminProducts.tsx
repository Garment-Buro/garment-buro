'use client';

import { useMemo, useState, type FormEvent } from 'react';
import {
    PiCheck,
    PiImage,
    PiPackage,
    PiPencilSimple,
    PiPlus,
} from 'react-icons/pi';
import { useAssortmentResource } from '@/hooks/production/useAssortmentResource';
import {
    assortmentRequest,
    saveAssortment,
    uploadAssortmentMedia,
} from '@/lib/api/productionAssortment';
import type {
    Fabric,
    GarmentModel,
    ProductCategory,
    ProductDetail,
    ProductReference,
    ProductVariantReference,
    ReferencePage,
} from '@/lib/production/assortmentTypes';
import { safeImage } from '@/lib/production/workflow';
import {
    AssortmentDialog,
    AssortmentFeedback,
    FileUploadStatus,
    idleFileUploadStatus,
    type FileUploadStatusValue,
} from './AssortmentDialog';
import styles from '../ProductionAdmin.module.css';

type ProductEditor = ProductDetail & {
    slug: string;
    category_id: number | null;
    garment_model_id: number | null;
    variantReferences: ProductVariantReference[];
};
type CategoryEditor = Partial<ProductCategory> & {
    slug: string;
    name: string;
    description: string | null;
    is_active: boolean;
};

const emptyProduct = (): ProductEditor => ({
    id: 0,
    title: '',
    slug: '',
    category_id: null,
    garment_model_id: null,
    price: 0,
    old_price: null,
    description: null,
    composition: null,
    model_info: null,
    sizes: '',
    colors: '',
    is_active: true,
    type: 'normal',
    weight: 0,
    height: 0,
    width: 0,
    length: 0,
    stock_quantity: 0,
    video_src: null,
    image_left: null,
    image_right: null,
    gallery_images: null,
    size_chart_img_1: null,
    size_chart_img_2: null,
    desktop_video: null,
    desktop_video_poster: null,
    desktop_card_images: null,
    desktop_slider_images: null,
    mobile_card_image: null,
    mobile_video_poster: null,
    mobile_slider_images: null,
    mobile_product_slider_images: null,
    mobile_size_chart_first: null,
    variants: [],
    variantReferences: [],
});

const productPrice = (value: string | number) =>
    new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB',
        maximumFractionDigits: 2,
    }).format(Number(value));

export function AdminProducts() {
    const products = useAssortmentResource<ProductReference[]>('products');
    const categories =
        useAssortmentResource<ProductCategory[]>('product-categories');
    const models = useAssortmentResource<ReferencePage<GarmentModel>>('models');
    const fabrics = useAssortmentResource<ReferencePage<Fabric>>('fabrics');
    const [search, setSearch] = useState('');
    const [editor, setEditor] = useState<ProductEditor | null>(null);
    const [categoryEditor, setCategoryEditor] = useState<CategoryEditor | null>(null);
    const [loadingEditor, setLoadingEditor] = useState(false);
    const [saving, setSaving] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [uploadStatus, setUploadStatus] =
        useState<FileUploadStatusValue>(idleFileUploadStatus);
    const [formError, setFormError] = useState('');
    const visibleProducts = useMemo(() => {
        const query = search.trim().toLocaleLowerCase('ru');
        const rows = products.data ?? [];
        return query
            ? rows.filter((product) =>
                  `${product.title} ${product.slug ?? ''}`
                      .toLocaleLowerCase('ru')
                      .includes(query),
              )
            : rows;
    }, [products.data, search]);
    const categoryName = (id: number | null) =>
        categories.data?.find((category) => category.id === id)?.name ??
        'Без категории';
    const modelName = (id: number | null) =>
        models.data?.items.find((model) => model.id === id)?.name ??
        'Модель не назначена';
    const selectedModel = models.data?.items.find(
        (model) => model.id === editor?.garment_model_id,
    );
    const selectedSizeIds = Array.from(
        new Set(
            (editor?.variantReferences ?? [])
                .map((reference) => reference.garment_size_id)
                .filter((id): id is number => id != null),
        ),
    );
    const selectedFabricIds = Array.from(
        new Set(
            (editor?.variantReferences ?? [])
                .map((reference) => reference.fabric_id)
                .filter((id): id is number => id != null),
        ),
    );

    const editProduct = async (reference: ProductReference) => {
        setLoadingEditor(true);
        setFormError('');
        try {
            const detail = await assortmentRequest<ProductDetail>(
                `products/${reference.id}`,
            );
            setEditor({
                ...detail,
                slug: reference.slug ?? '',
                category_id: reference.category_id,
                garment_model_id: reference.garment_model_id,
                variantReferences: reference.variants,
            });
            setUploadStatus(
                detail.image_left
                    ? {
                          state: 'success',
                          message: 'Основное изображение уже загружено',
                      }
                    : idleFileUploadStatus,
            );
        } catch (reason) {
            setFormError(
                reason instanceof Error
                    ? reason.message
                    : 'Не удалось открыть товар',
            );
        } finally {
            setLoadingEditor(false);
        }
    };
    const submitCategory = async (event: FormEvent) => {
        event.preventDefault();
        if (!categoryEditor) return;
        setSaving(true);
        setFormError('');
        try {
            await saveAssortment(
                categoryEditor.id
                    ? `product-categories/${categoryEditor.id}`
                    : 'product-categories',
                categoryEditor.id ? 'PUT' : 'POST',
                {
                    slug: categoryEditor.slug,
                    name: categoryEditor.name,
                    description: categoryEditor.description,
                    is_active: categoryEditor.is_active,
                    ...(categoryEditor.id
                        ? { expected_version: categoryEditor.version }
                        : {}),
                },
            );
            setCategoryEditor(null);
            categories.reload();
        } catch (reason) {
            setFormError(
                reason instanceof Error
                    ? reason.message
                    : 'Не удалось сохранить категорию',
            );
        } finally {
            setSaving(false);
        }
    };
    const submitProduct = async (event: FormEvent) => {
        event.preventDefault();
        if (!editor) return;
        setSaving(true);
        setFormError('');
        const payload = {
            title: editor.title,
            slug: editor.slug || null,
            category_id: editor.category_id,
            garment_model_id: editor.garment_model_id,
            price: Number(editor.price),
            old_price:
                editor.old_price == null ? null : Number(editor.old_price),
            description: editor.description,
            composition: editor.composition,
            model_info: editor.model_info,
            sizes: editor.sizes,
            colors: editor.colors,
            is_active: editor.is_active,
            type: editor.type,
            weight: Number(editor.weight),
            height: Number(editor.height),
            width: Number(editor.width),
            length: Number(editor.length),
            stock_quantity: Number(editor.stock_quantity),
            video_src: editor.video_src,
            image_left: editor.image_left,
            image_right: editor.image_right,
            gallery_images: editor.gallery_images,
            size_chart_img_1: editor.size_chart_img_1,
            size_chart_img_2: editor.size_chart_img_2,
            desktop_video: editor.desktop_video,
            desktop_video_poster: editor.desktop_video_poster,
            desktop_card_images: editor.desktop_card_images,
            desktop_slider_images: editor.desktop_slider_images,
            mobile_card_image: editor.mobile_card_image,
            mobile_video_poster: editor.mobile_video_poster,
            mobile_slider_images: editor.mobile_slider_images,
            mobile_product_slider_images:
                editor.mobile_product_slider_images,
            mobile_size_chart_first: editor.mobile_size_chart_first,
            variants: editor.variants.map((variant, index) => {
                const reference = editor.variantReferences[index];
                return {
                    id: variant.id || undefined,
                    size: variant.size,
                    garment_size_id: reference?.garment_size_id ?? null,
                    fabric_id: reference?.fabric_id ?? null,
                    color: variant.color,
                    color_hex: variant.color_hex,
                    stock_quantity: Number(variant.stock_quantity),
                    width_cm: variant.width_cm,
                    height_cm: variant.height_cm,
                    preview_image: variant.preview_image,
                    images: variant.images,
                };
            }),
        };
        try {
            await saveAssortment(
                editor.id ? `products/${editor.id}` : 'products',
                editor.id ? 'PUT' : 'POST',
                payload,
            );
            setEditor(null);
            products.reload();
        } catch (reason) {
            setFormError(
                reason instanceof Error
                    ? reason.message
                    : 'Не удалось сохранить товар',
            );
        } finally {
            setSaving(false);
        }
    };
    const updateVariant = (
        index: number,
        changes: Partial<ProductDetail['variants'][number]>,
        referenceChanges?: Partial<ProductVariantReference>,
    ) => {
        setEditor((current) => {
            if (!current) return current;
            const variants = [...current.variants];
            variants[index] = { ...variants[index], ...changes };
            const variantReferences = [...current.variantReferences];
            const existingReference = variantReferences[index] ?? {
                id: variants[index].id,
                sku: null,
                size: null,
                garment_size_id: null,
                fabric_id: null,
                color: null,
                stock_quantity: 0,
            };
            variantReferences[index] = {
                ...existingReference,
                size: changes.size ?? variants[index].size,
                color: changes.color ?? variants[index].color,
                stock_quantity:
                    changes.stock_quantity ?? variants[index].stock_quantity,
                ...referenceChanges,
            };
            return { ...current, variants, variantReferences };
        });
    };
    const rebuildVariantMatrix = (
        sizeIds: number[],
        fabricIds: number[],
    ) => {
        setEditor((current) => {
            if (!current) return current;
            const selectedModel = models.data?.items.find(
                (model) => model.id === current.garment_model_id,
            );
            const existing = new Map(
                current.variantReferences.map((reference, index) => [
                    `${reference.garment_size_id ?? ''}:${reference.fabric_id ?? ''}`,
                    { variant: current.variants[index], reference },
                ]),
            );
            const combinations =
                sizeIds.length === 0 && fabricIds.length === 0
                    ? []
                    : (sizeIds.length ? sizeIds : [null]).flatMap((sizeId) =>
                          (fabricIds.length ? fabricIds : [null]).map(
                              (fabricId) => ({ sizeId, fabricId }),
                          ),
                      );
            const next = combinations.map(({ sizeId, fabricId }) => {
                const key = `${sizeId ?? ''}:${fabricId ?? ''}`;
                const previous = existing.get(key);
                if (previous) return previous;
                const size = selectedModel?.sizes.find(
                    (item) => item.id === sizeId,
                );
                const fabric = fabrics.data?.items.find(
                    (item) => item.id === fabricId,
                );
                return {
                    variant: {
                        id: 0,
                        size: size?.code ?? null,
                        color: fabric?.color_name ?? null,
                        color_hex: fabric?.color_hex ?? null,
                        stock_quantity: 0,
                        width_cm: null,
                        height_cm: null,
                        preview_image: null,
                        images: null,
                    },
                    reference: {
                        id: 0,
                        sku: null,
                        size: size?.code ?? null,
                        garment_size_id: sizeId,
                        fabric_id: fabricId,
                        color: fabric?.color_name ?? null,
                        stock_quantity: 0,
                    },
                };
            });
            return {
                ...current,
                variants: next.map((item) => item.variant),
                variantReferences: next.map((item) => item.reference),
            };
        });
    };

    return (
        <section aria-busy={products.loading || loadingEditor}>
            <div className={styles.assortmentHeading}>
                <div>
                    <h3>Товары</h3>
                    <p className={styles.muted}>
                        Каталог, цены, остатки, варианты и связь с производственной моделью.
                    </p>
                </div>
                <div className={styles.headingActions}>
                    <button
                        onClick={() =>
                            setCategoryEditor({
                                slug: '',
                                name: '',
                                description: null,
                                is_active: true,
                            })
                        }
                    >
                        <PiPlus aria-hidden /> Категория
                    </button>
                    <button
                        onClick={() => {
                            setUploadStatus(idleFileUploadStatus);
                            setEditor(emptyProduct());
                        }}
                    >
                        <PiPlus aria-hidden /> Добавить товар
                    </button>
                </div>
            </div>
            <div className={styles.chipList} aria-label="Категории товаров">
                {(categories.data ?? []).map((category) => (
                    <button
                        key={category.id}
                        onClick={() => setCategoryEditor({ ...category })}
                    >
                        {category.name}
                    </button>
                ))}
            </div>
            <label className={styles.assortmentSearch}>
                Поиск товара
                <input
                    value={search}
                    placeholder="Название или slug"
                    onChange={(event) => setSearch(event.target.value)}
                />
            </label>
            {formError && !editor && !categoryEditor && (
                <p className={styles.error}>{formError}</p>
            )}
            <AssortmentFeedback
                loading={products.loading}
                error={products.error}
                empty={!products.loading && visibleProducts.length === 0}
            />
            <div className={styles.productGrid}>
                {visibleProducts.map((product) => {
                    const image = safeImage(product.image_url);
                    const sku = product.variants.find((variant) => variant.sku)?.sku;
                    return (
                        <article className={styles.productCard} key={product.id}>
                            <div className={styles.productMedia}>
                                {image ? (
                                    // eslint-disable-next-line @next/next/no-img-element
                                    <img
                                        src={image}
                                        alt={product.title}
                                        loading="lazy"
                                    />
                                ) : (
                                    <span className={styles.productMediaFallback}>
                                        <PiImage aria-hidden />
                                        <small>Нет фото</small>
                                    </span>
                                )}
                                <span
                                    className={styles.productStatus}
                                    data-active={product.is_active}
                                >
                                    {product.is_active ? 'В продаже' : 'Скрыт'}
                                </span>
                            </div>
                            <div className={styles.productCardBody}>
                                <div className={styles.productCardHeader}>
                                    <div className={styles.productIdentity}>
                                        <span className={styles.productCategory}>
                                            {categoryName(product.category_id)}
                                        </span>
                                        <h4>{product.title}</h4>
                                        <small>
                                            {sku
                                                ? `Артикул ${sku}`
                                                : `/${product.slug ?? `product-${product.id}`}`}
                                        </small>
                                    </div>
                                    <button
                                        className={styles.iconButton}
                                        disabled={loadingEditor}
                                        onClick={() => void editProduct(product)}
                                        aria-label={`Изменить товар ${product.title}`}
                                        title="Изменить"
                                    >
                                        <PiPencilSimple aria-hidden />
                                    </button>
                                </div>
                                <p className={styles.productModel}>
                                    <PiPackage aria-hidden />
                                    <span>{modelName(product.garment_model_id)}</span>
                                </p>
                                <dl className={styles.productFacts}>
                                    <div>
                                        <dt>Цена</dt>
                                        <dd>{productPrice(product.price)}</dd>
                                    </div>
                                    <div>
                                        <dt>Остаток</dt>
                                        <dd>{product.stock_quantity} шт.</dd>
                                    </div>
                                    <div>
                                        <dt>Варианты</dt>
                                        <dd>{product.variants.length}</dd>
                                    </div>
                                </dl>
                            </div>
                        </article>
                    );
                })}
            </div>
            {categoryEditor && (
                <AssortmentDialog
                    title={categoryEditor.id ? 'Изменить категорию' : 'Новая категория'}
                    onClose={() => setCategoryEditor(null)}
                >
                    <form onSubmit={submitCategory}>
                        <div className={styles.formGrid}>
                            <label>
                                Название
                                <input
                                    required
                                    value={categoryEditor.name}
                                    onChange={(event) =>
                                        setCategoryEditor({
                                            ...categoryEditor,
                                            name: event.target.value,
                                        })
                                    }
                                />
                            </label>
                            <label>
                                Slug
                                <input
                                    required
                                    pattern="[a-z0-9][a-z0-9-]*"
                                    value={categoryEditor.slug}
                                    onChange={(event) =>
                                        setCategoryEditor({
                                            ...categoryEditor,
                                            slug: event.target.value.toLowerCase(),
                                        })
                                    }
                                />
                            </label>
                            <label className={styles.fullField}>
                                Описание
                                <textarea
                                    value={categoryEditor.description ?? ''}
                                    onChange={(event) =>
                                        setCategoryEditor({
                                            ...categoryEditor,
                                            description: event.target.value || null,
                                        })
                                    }
                                />
                            </label>
                            <label className={styles.checkField}>
                                <input
                                    type="checkbox"
                                    checked={categoryEditor.is_active}
                                    onChange={(event) =>
                                        setCategoryEditor({
                                            ...categoryEditor,
                                            is_active: event.target.checked,
                                        })
                                    }
                                />
                                Категория активна
                            </label>
                        </div>
                        {formError && <p className={styles.error}>{formError}</p>}
                        <div className={styles.editorActions}>
                            <button type="button" onClick={() => setCategoryEditor(null)}>
                                Отмена
                            </button>
                            <button className={styles.primaryButton} disabled={saving}>
                                Сохранить
                            </button>
                        </div>
                    </form>
                </AssortmentDialog>
            )}
            {editor && (
                <AssortmentDialog
                    title={editor.id ? 'Изменить товар' : 'Новый товар'}
                    description="Основные данные каталога и точные производственные ссылки вариантов."
                    onClose={() => setEditor(null)}
                >
                    <form onSubmit={submitProduct}>
                        <fieldset className={styles.formSection}>
                            <legend>Карточка товара</legend>
                            <div className={styles.formGrid}>
                                <label className={styles.fullField}>
                                    Название
                                    <input
                                        required
                                        value={editor.title}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                title: event.target.value,
                                            })
                                        }
                                    />
                                </label>
                                <label>
                                    Slug
                                    <input
                                        pattern="[a-z0-9][a-z0-9-]*"
                                        value={editor.slug}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                slug: event.target.value.toLowerCase(),
                                            })
                                        }
                                    />
                                </label>
                                <label>
                                    Категория
                                    <select
                                        value={editor.category_id ?? ''}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                category_id: event.target.value
                                                    ? Number(event.target.value)
                                                    : null,
                                            })
                                        }
                                    >
                                        <option value="">Без категории</option>
                                        {(categories.data ?? []).map((category) => (
                                            <option key={category.id} value={category.id}>
                                                {category.name}
                                            </option>
                                        ))}
                                    </select>
                                </label>
                                <label>
                                    Производственная модель
                                    <select
                                        value={editor.garment_model_id ?? ''}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                garment_model_id: event.target.value
                                                    ? Number(event.target.value)
                                                    : null,
                                                variants: [],
                                                variantReferences: [],
                                            })
                                        }
                                    >
                                        <option value="">Не назначена</option>
                                        {(models.data?.items ?? []).map((model) => (
                                            <option key={model.id} value={model.id}>
                                                {model.name}
                                            </option>
                                        ))}
                                    </select>
                                </label>
                                <label>
                                    Цена
                                    <input
                                        required
                                        type="number"
                                        min="0"
                                        step="0.01"
                                        value={editor.price}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                price: Number(event.target.value),
                                            })
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
                                            setEditor({
                                                ...editor,
                                                old_price: event.target.value
                                                    ? Number(event.target.value)
                                                    : null,
                                            })
                                        }
                                    />
                                </label>
                                <label>
                                    Общий остаток
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
                                    Вес, кг
                                    <input
                                        type="number"
                                        min="0"
                                        step="0.01"
                                        value={editor.weight}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                weight: Number(event.target.value),
                                            })
                                        }
                                    />
                                </label>
                                <label className={styles.fullField}>
                                    Описание
                                    <textarea
                                        value={editor.description ?? ''}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                description:
                                                    event.target.value || null,
                                            })
                                        }
                                    />
                                </label>
                                <label className={styles.fullField}>
                                    Состав
                                    <input
                                        value={editor.composition ?? ''}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                composition:
                                                    event.target.value || null,
                                            })
                                        }
                                    />
                                </label>
                                <div className={`${styles.fullField} ${styles.productImageField}`}>
                                    <div className={styles.productImagePreview}>
                                        {safeImage(editor.image_left) ? (
                                            // eslint-disable-next-line @next/next/no-img-element
                                            <img
                                                src={safeImage(editor.image_left) ?? ''}
                                                alt="Превью товара"
                                            />
                                        ) : (
                                            <PiImage aria-hidden />
                                        )}
                                    </div>
                                    <label>
                                        Основное изображение
                                        <input
                                            type="file"
                                            accept="image/jpeg,image/png,image/webp"
                                            disabled={uploading}
                                            onChange={async (event) => {
                                                const file = event.target.files?.[0];
                                                if (!file) return;
                                                setUploading(true);
                                                setFormError('');
                                                setUploadStatus({
                                                    state: 'uploading',
                                                    fileName: file.name,
                                                });
                                                try {
                                                    const media =
                                                        await uploadAssortmentMedia(
                                                            file,
                                                            'public',
                                                        );
                                                    setEditor((current) =>
                                                        current
                                                            ? {
                                                                  ...current,
                                                                  image_left:
                                                                      media.url ?? null,
                                                              }
                                                            : current,
                                                    );
                                                    setUploadStatus({
                                                        state: 'success',
                                                        fileName: file.name,
                                                    });
                                                } catch (reason) {
                                                    const message =
                                                        reason instanceof Error
                                                            ? reason.message
                                                            : 'Не удалось загрузить изображение';
                                                    setFormError(message);
                                                    setUploadStatus({
                                                        state: 'error',
                                                        fileName: file.name,
                                                        message,
                                                    });
                                                } finally {
                                                    setUploading(false);
                                                }
                                            }}
                                        />
                                        <small>JPEG, PNG или WebP</small>
                                    </label>
                                    <FileUploadStatus value={uploadStatus} />
                                </div>
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
                                    Товар активен
                                </label>
                            </div>
                        </fieldset>
                        <fieldset className={styles.formSection}>
                            <legend>Варианты</legend>
                            {!selectedModel ? (
                                <p className={styles.muted}>
                                    Сначала выберите производственную модель.
                                </p>
                            ) : (
                                <div className={styles.variantBuilder}>
                                    <section>
                                        <h4>Размеры</h4>
                                        <div className={styles.variantChoiceGrid}>
                                            {selectedModel.sizes.map((size) => {
                                                const selected =
                                                    size.id != null &&
                                                    selectedSizeIds.includes(size.id);
                                                return (
                                                    <button
                                                        type="button"
                                                        key={size.id ?? size.code}
                                                        data-selected={selected}
                                                        aria-pressed={selected}
                                                        onClick={() => {
                                                            if (size.id == null) return;
                                                            rebuildVariantMatrix(
                                                                selected
                                                                    ? selectedSizeIds.filter(
                                                                          (id) =>
                                                                              id !== size.id,
                                                                      )
                                                                    : [
                                                                          ...selectedSizeIds,
                                                                          size.id,
                                                                      ],
                                                                selectedFabricIds,
                                                            );
                                                        }}
                                                    >
                                                        <PiCheck aria-hidden />
                                                        <strong>{size.code}</strong>
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    </section>
                                    <section>
                                        <h4>Ткани и цвета</h4>
                                        <div className={styles.variantChoiceGrid}>
                                            {(fabrics.data?.items ?? []).map(
                                                (fabric) => {
                                                    const selected =
                                                        selectedFabricIds.includes(
                                                            fabric.id,
                                                        );
                                                    return (
                                                        <button
                                                            type="button"
                                                            key={fabric.id}
                                                            data-selected={selected}
                                                            aria-pressed={selected}
                                                            onClick={() =>
                                                                rebuildVariantMatrix(
                                                                    selectedSizeIds,
                                                                    selected
                                                                        ? selectedFabricIds.filter(
                                                                              (id) =>
                                                                                  id !==
                                                                                  fabric.id,
                                                                          )
                                                                        : [
                                                                              ...selectedFabricIds,
                                                                              fabric.id,
                                                                          ],
                                                                )
                                                            }
                                                        >
                                                            <span
                                                                className={
                                                                    styles.variantColor
                                                                }
                                                                style={{
                                                                    background:
                                                                        fabric.color_hex ??
                                                                        '#f2f0ef',
                                                                }}
                                                            />
                                                            <PiCheck aria-hidden />
                                                            <strong>
                                                                {fabric.color_name ||
                                                                    fabric.name}
                                                            </strong>
                                                            <small>{fabric.name}</small>
                                                        </button>
                                                    );
                                                },
                                            )}
                                        </div>
                                    </section>
                                    {editor.variants.length > 0 && (
                                        <section>
                                            <div className={styles.variantSummaryHeading}>
                                                <h4>Созданные варианты</h4>
                                                <span>
                                                    {editor.variants.length} шт.
                                                </span>
                                            </div>
                                            <div className={styles.variantRows}>
                                                {editor.variants.map(
                                                    (variant, index) => (
                                                        <article
                                                            key={`${editor.variantReferences[index]?.garment_size_id}-${editor.variantReferences[index]?.fabric_id}`}
                                                        >
                                                            <div>
                                                                <strong>
                                                                    {variant.size ??
                                                                        'Все размеры'}
                                                                </strong>
                                                                <small>
                                                                    {variant.color ??
                                                                        'Без ткани'}
                                                                </small>
                                                            </div>
                                                            <label>
                                                                Остаток
                                                                <input
                                                                    type="number"
                                                                    min="0"
                                                                    value={
                                                                        variant.stock_quantity
                                                                    }
                                                                    onChange={(event) =>
                                                                        updateVariant(
                                                                            index,
                                                                            {
                                                                                stock_quantity:
                                                                                    Number(
                                                                                        event
                                                                                            .target
                                                                                            .value,
                                                                                    ),
                                                                            },
                                                                        )
                                                                    }
                                                                />
                                                            </label>
                                                        </article>
                                                    ),
                                                )}
                                            </div>
                                        </section>
                                    )}
                                </div>
                            )}
                        </fieldset>
                        {formError && <p className={styles.error}>{formError}</p>}
                        <div className={styles.editorActions}>
                            <button type="button" onClick={() => setEditor(null)}>
                                Отмена
                            </button>
                            <button
                                className={styles.primaryButton}
                                disabled={saving || uploading}
                            >
                                {saving ? 'Сохраняем…' : 'Сохранить товар'}
                            </button>
                        </div>
                    </form>
                </AssortmentDialog>
            )}
        </section>
    );
}
