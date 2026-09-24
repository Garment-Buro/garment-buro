'use client';

import { useMemo, useState, type FormEvent } from 'react';
import { PiLink, PiPencilSimple, PiPlus } from 'react-icons/pi';
import { useAssortmentResource } from '@/hooks/production/useAssortmentResource';
import { saveAssortment } from '@/lib/api/productionAssortment';
import type {
    Fabric,
    FabricRequirement,
    GarmentModel,
    ReferencePage,
} from '@/lib/production/assortmentTypes';
import { compactDecimal } from '@/lib/production/numbers';
import { AdminFilters } from '../AdminFilters';
import { AssortmentDialog, AssortmentFeedback } from './AssortmentDialog';
import styles from '../ProductionAdmin.module.css';

type FabricForm = Omit<Fabric, 'id' | 'version' | 'balance'> & {
    id?: number;
    version?: number;
};

const emptyFabric = (): FabricForm => ({
    code: '',
    name: '',
    material_type: null,
    color_name: '',
    color_hex: null,
    density_gsm: null,
    width_cm: '150',
    cost_per_meter: null,
    minimum_stock_meters: '0',
    currency: 'RUB',
    is_active: true,
});

type RequirementForm = Partial<FabricRequirement> & {
    garment_model_id: number;
    fabric_id: number;
    meters_per_unit: string;
    waste_percent: string;
    is_primary: boolean;
};

export function AdminFabrics() {
    const fabricsResource =
        useAssortmentResource<ReferencePage<Fabric>>('fabrics');
    const modelsResource =
        useAssortmentResource<ReferencePage<GarmentModel>>('models');
    const requirementsResource =
        useAssortmentResource<FabricRequirement[]>('fabric-requirements');
    const [search, setSearch] = useState('');
    const [activityFilter, setActivityFilter] = useState('');
    const [stockFilter, setStockFilter] = useState('');
    const [sorting, setSorting] = useState('name:asc');
    const [editor, setEditor] = useState<FabricForm | null>(null);
    const [requirementEditor, setRequirementEditor] =
        useState<RequirementForm | null>(null);
    const [saving, setSaving] = useState(false);
    const [formError, setFormError] = useState('');
    const fabrics = useMemo(() => {
        const query = search.trim().toLocaleLowerCase('ru');
        const rows = fabricsResource.data?.items ?? [];
        const filtered = (query
            ? rows.filter((fabric) =>
                  `${fabric.name} ${fabric.code} ${fabric.color_name}`
                      .toLocaleLowerCase('ru')
                      .includes(query),
              )
            : rows
        ).filter((fabric) => {
            const available = Number(fabric.balance?.available_quantity ?? 0);
            const minimum = Number(fabric.minimum_stock_meters);
            return (
                (!activityFilter ||
                    fabric.is_active === (activityFilter === 'active')) &&
                (!stockFilter ||
                    (stockFilter === 'low'
                        ? available <= minimum
                        : available > minimum))
            );
        });
        const [field, direction] = sorting.split(':');
        return [...filtered].sort((left, right) => {
            const values: Record<string, [string | number, string | number]> = {
                name: [left.name, right.name],
                code: [left.code, right.code],
                stock: [
                    Number(left.balance?.available_quantity ?? 0),
                    Number(right.balance?.available_quantity ?? 0),
                ],
                price: [
                    Number(left.cost_per_meter ?? 0),
                    Number(right.cost_per_meter ?? 0),
                ],
            };
            const [a, b] = values[field] ?? values.name;
            const result =
                typeof a === 'number' && typeof b === 'number'
                    ? a - b
                    : String(a).localeCompare(String(b), 'ru');
            return direction === 'desc' ? -result : result;
        });
    }, [activityFilter, fabricsResource.data, search, sorting, stockFilter]);

    const submitFabric = async (event: FormEvent) => {
        event.preventDefault();
        if (!editor) return;
        setSaving(true);
        setFormError('');
        try {
            await saveAssortment(
                editor.id ? `fabrics/${editor.id}` : 'fabrics',
                editor.id ? 'PUT' : 'POST',
                {
                    ...editor,
                    width_cm: Number(editor.width_cm),
                    density_gsm: editor.density_gsm
                        ? Number(editor.density_gsm)
                        : null,
                    cost_per_meter: editor.cost_per_meter
                        ? Number(editor.cost_per_meter)
                        : null,
                    minimum_stock_meters: Number(
                        editor.minimum_stock_meters || 0,
                    ),
                    ...(editor.id ? { expected_version: editor.version } : {}),
                    id: undefined,
                    version: undefined,
                },
            );
            setEditor(null);
            fabricsResource.reload();
        } catch (reason) {
            setFormError(
                reason instanceof Error
                    ? reason.message
                    : 'Не удалось сохранить ткань',
            );
        } finally {
            setSaving(false);
        }
    };

    const submitRequirement = async (event: FormEvent) => {
        event.preventDefault();
        if (!requirementEditor) return;
        setSaving(true);
        setFormError('');
        try {
            await saveAssortment(
                requirementEditor.id
                    ? `fabric-requirements/${requirementEditor.id}`
                    : 'fabric-requirements',
                requirementEditor.id ? 'PUT' : 'POST',
                {
                    garment_model_id: requirementEditor.garment_model_id,
                    fabric_id: requirementEditor.fabric_id,
                    meters_per_unit: Number(
                        requirementEditor.meters_per_unit,
                    ),
                    waste_percent: Number(
                        requirementEditor.waste_percent || 0,
                    ),
                    is_primary: requirementEditor.is_primary,
                    ...(requirementEditor.id
                        ? { expected_version: requirementEditor.version }
                        : {}),
                },
            );
            setRequirementEditor(null);
            requirementsResource.reload();
        } catch (reason) {
            setFormError(
                reason instanceof Error
                    ? reason.message
                    : 'Не удалось сохранить расход ткани',
            );
        } finally {
            setSaving(false);
        }
    };

    const modelName = (id: number) =>
        modelsResource.data?.items.find((item) => item.id === id)?.name ??
        `Модель №${id}`;
    const fabricName = (id: number) =>
        fabricsResource.data?.items.find((item) => item.id === id)?.name ??
        `Ткань №${id}`;

    return (
        <section aria-busy={fabricsResource.loading}>
            <div className={styles.assortmentHeading}>
                <div>
                    <h3>Ткани</h3>
                    <p className={styles.muted}>
                        Карточки тканей, остатки и нормативный расход на изделие.
                    </p>
                </div>
                <div className={styles.headingActions}>
                    <button onClick={() => setRequirementEditor({
                        garment_model_id: modelsResource.data?.items[0]?.id ?? 0,
                        fabric_id: fabricsResource.data?.items[0]?.id ?? 0,
                        meters_per_unit: '1',
                        waste_percent: '0',
                        is_primary: false,
                    })}>
                        <PiLink aria-hidden /> Задать расход
                    </button>
                    <button onClick={() => setEditor(emptyFabric())}>
                        <PiPlus aria-hidden /> Добавить ткань
                    </button>
                </div>
            </div>
            <div className={styles.assortmentFilters}>
                <label className={styles.assortmentSearch}>
                    Поиск ткани
                    <input
                        type="search"
                        value={search}
                        placeholder="Название, код или цвет"
                        onChange={(event) => setSearch(event.target.value)}
                    />
                </label>
                <AdminFilters
                    groups={[
                        {
                            key: 'activity',
                            label: 'Видимость',
                            options: [
                                ['', 'Все ткани'],
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
                                ['price:asc', 'Сначала дешевле'],
                                ['price:desc', 'Сначала дороже'],
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
                loading={fabricsResource.loading}
                error={fabricsResource.error}
                empty={!fabricsResource.loading && fabrics.length === 0}
            />
            {fabrics.length > 0 && (
                <div className={styles.tableScroll} tabIndex={0}>
                    <table>
                        <thead>
                            <tr>
                                <th>Ткань</th>
                                <th>Характеристики</th>
                                <th>Остаток</th>
                                <th>Цена</th>
                                <th>Действие</th>
                            </tr>
                        </thead>
                        <tbody>
                            {fabrics.map((fabric) => (
                                <tr key={fabric.id}>
                                    <td data-label="Ткань">
                                        <strong>{fabric.name}</strong>
                                        <small>{fabric.code}</small>
                                    </td>
                                    <td data-label="Характеристики">
                                        {fabric.color_name},{' '}
                                        {compactDecimal(fabric.width_cm)} см
                                        <small>
                                            {fabric.material_type ?? 'Состав не указан'}
                                        </small>
                                    </td>
                                    <td data-label="Остаток">
                                        {compactDecimal(
                                            fabric.balance?.available_quantity ?? '0',
                                        )}{' '}
                                        м
                                        <small>
                                            Минимум{' '}
                                            {compactDecimal(
                                                fabric.minimum_stock_meters,
                                            )}{' '}
                                            м
                                        </small>
                                    </td>
                                    <td data-label="Цена">
                                        {fabric.cost_per_meter
                                            ? `${compactDecimal(fabric.cost_per_meter)} ₽/м`
                                            : 'Не задана'}
                                    </td>
                                    <td data-label="Действие">
                                        <button
                                            onClick={() =>
                                                setEditor({
                                                    ...fabric,
                                                    density_gsm: fabric.density_gsm
                                                        ? compactDecimal(
                                                              fabric.density_gsm,
                                                          )
                                                        : null,
                                                    width_cm: compactDecimal(
                                                        fabric.width_cm,
                                                    ),
                                                    cost_per_meter:
                                                        fabric.cost_per_meter
                                                            ? compactDecimal(
                                                                  fabric.cost_per_meter,
                                                              )
                                                            : null,
                                                    minimum_stock_meters:
                                                        compactDecimal(
                                                            fabric.minimum_stock_meters,
                                                        ),
                                                })
                                            }
                                        >
                                            <PiPencilSimple aria-hidden /> Изменить
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
            <section className={styles.relatedSection}>
                <h4>Расход ткани по моделям</h4>
                {requirementsResource.error && (
                    <p className={styles.error}>{requirementsResource.error}</p>
                )}
                <div className={styles.relationshipList}>
                    {(requirementsResource.data ?? []).map((item) => (
                        <button
                            key={item.id}
                            className={styles.relationshipCard}
                            onClick={() =>
                                setRequirementEditor({
                                    ...item,
                                    meters_per_unit: compactDecimal(
                                        item.meters_per_unit,
                                    ),
                                    waste_percent: compactDecimal(
                                        item.waste_percent,
                                    ),
                                })
                            }
                        >
                            <span>
                                <strong>{modelName(item.garment_model_id)}</strong>
                                <small>{fabricName(item.fabric_id)}</small>
                            </span>
                            <span>
                                {compactDecimal(item.meters_per_unit)} м +{' '}
                                {compactDecimal(item.waste_percent)}%
                            </span>
                        </button>
                    ))}
                </div>
            </section>
            {editor && (
                <AssortmentDialog
                    title={editor.id ? 'Изменить ткань' : 'Новая ткань'}
                    onClose={() => setEditor(null)}
                >
                    <form onSubmit={submitFabric}>
                        <div className={styles.formGrid}>
                            {(
                                [
                                    ['name', 'Название', 'text'],
                                    ['code', 'Код', 'text'],
                                    ['material_type', 'Состав', 'text'],
                                    ['color_name', 'Цвет', 'text'],
                                    ['color_hex', 'HEX цвета', 'text'],
                                    ['width_cm', 'Ширина, см', 'number'],
                                    ['density_gsm', 'Плотность, г/м²', 'number'],
                                    ['cost_per_meter', 'Цена за метр', 'number'],
                                    [
                                        'minimum_stock_meters',
                                        'Минимальный остаток, м',
                                        'number',
                                    ],
                                ] as const
                            ).map(([field, label, type]) => (
                                <label key={field}>
                                    {label}
                                    <input
                                        required={['name', 'code', 'color_name', 'width_cm'].includes(field)}
                                        type={type}
                                        min={type === 'number' ? '0' : undefined}
                                        step={type === 'number' ? '0.01' : undefined}
                                        value={editor[field] ?? ''}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                [field]: event.target.value || null,
                                            })
                                        }
                                    />
                                </label>
                            ))}
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
                                Ткань активна
                            </label>
                        </div>
                        {formError && <p className={styles.error}>{formError}</p>}
                        <div className={styles.editorActions}>
                            <button type="button" onClick={() => setEditor(null)}>
                                Отмена
                            </button>
                            <button className={styles.primaryButton} disabled={saving}>
                                {saving ? 'Сохраняем…' : 'Сохранить'}
                            </button>
                        </div>
                    </form>
                </AssortmentDialog>
            )}
            {requirementEditor && (
                <AssortmentDialog
                    title="Расход ткани"
                    description="Количество ткани на одно изделие с технологическим запасом."
                    onClose={() => setRequirementEditor(null)}
                >
                    <form onSubmit={submitRequirement}>
                        <div className={styles.formGrid}>
                            <label>
                                Модель
                                <select
                                    required
                                    value={requirementEditor.garment_model_id || ''}
                                    onChange={(event) =>
                                        setRequirementEditor({
                                            ...requirementEditor,
                                            garment_model_id: Number(event.target.value),
                                        })
                                    }
                                >
                                    <option value="">Выберите модель</option>
                                    {(modelsResource.data?.items ?? []).map((model) => (
                                        <option key={model.id} value={model.id}>
                                            {model.name}
                                        </option>
                                    ))}
                                </select>
                            </label>
                            <label>
                                Ткань
                                <select
                                    required
                                    value={requirementEditor.fabric_id || ''}
                                    onChange={(event) =>
                                        setRequirementEditor({
                                            ...requirementEditor,
                                            fabric_id: Number(event.target.value),
                                        })
                                    }
                                >
                                    <option value="">Выберите ткань</option>
                                    {(fabricsResource.data?.items ?? []).map((fabric) => (
                                        <option key={fabric.id} value={fabric.id}>
                                            {fabric.name}
                                        </option>
                                    ))}
                                </select>
                            </label>
                            <label>
                                Метров на изделие
                                <input
                                    required
                                    type="number"
                                min="0.1"
                                step="0.1"
                                    value={requirementEditor.meters_per_unit}
                                    onChange={(event) =>
                                        setRequirementEditor({
                                            ...requirementEditor,
                                            meters_per_unit: event.target.value,
                                        })
                                    }
                                />
                            </label>
                            <label>
                                Запас на отходы, %
                                <input
                                    type="number"
                                    min="0"
                                    max="100"
                                    step="0.01"
                                    value={requirementEditor.waste_percent}
                                    onChange={(event) =>
                                        setRequirementEditor({
                                            ...requirementEditor,
                                            waste_percent: event.target.value,
                                        })
                                    }
                                />
                            </label>
                            <label className={styles.checkField}>
                                <input
                                    type="checkbox"
                                    checked={requirementEditor.is_primary}
                                    onChange={(event) =>
                                        setRequirementEditor({
                                            ...requirementEditor,
                                            is_primary: event.target.checked,
                                        })
                                    }
                                />
                                Основная ткань модели
                            </label>
                        </div>
                        {formError && <p className={styles.error}>{formError}</p>}
                        <div className={styles.editorActions}>
                            <button
                                type="button"
                                onClick={() => setRequirementEditor(null)}
                            >
                                Отмена
                            </button>
                            <button className={styles.primaryButton} disabled={saving}>
                                {saving ? 'Сохраняем…' : 'Сохранить расход'}
                            </button>
                        </div>
                    </form>
                </AssortmentDialog>
            )}
        </section>
    );
}
