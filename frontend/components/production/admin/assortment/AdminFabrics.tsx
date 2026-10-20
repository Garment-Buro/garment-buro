'use client';

import { useState, type FormEvent } from 'react';
import { PiLink, PiPencilSimple, PiPlus } from 'react-icons/pi';
import { useFabricDirectory, useFabricRequirements } from '@/hooks/production/useReferenceDirectory';
import { ReferencePicker } from './ReferencePicker';
import { saveAssortment } from '@/lib/api/productionAssortment';
import type {
    Fabric,
    FabricRequirement,
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
    cost_per_kg: null,
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
    const [search, setSearch] = useState('');
    const [activityFilter, setActivityFilter] = useState('');
    const [stockFilter, setStockFilter] = useState('');
    const [sorting, setSorting] = useState('name:asc');
    const [editor, setEditor] = useState<FabricForm | null>(null);
    const [requirementEditor, setRequirementEditor] =
        useState<RequirementForm | null>(null);
    const [saving, setSaving] = useState(false);
    const [formError, setFormError] = useState('');
    const fabricsResource = useFabricDirectory({query:search,active:activityFilter?activityFilter==='active':undefined,stock:stockFilter||'all',sort:sorting,limit:24});
    const requirementsResource = useFabricRequirements();
    const fabrics = fabricsResource.items;

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
                    code:editor.code,name:editor.name,material_type:editor.material_type,
                    color_name:editor.color_name,color_hex:editor.color_hex,currency:editor.currency,is_active:editor.is_active,
                    cost_per_meter:editor.cost_per_meter===null?null:Number(editor.cost_per_meter),
                    width_cm: Number(editor.width_cm),
                    density_gsm: editor.density_gsm
                        ? Number(editor.density_gsm)
                        : null,
                    cost_per_kg: editor.cost_per_kg
                        ? Number(editor.cost_per_kg)
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
            fabricsResource.retry();
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
            requirementsResource.retry();
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
                        garment_model_id: 0,
                        fabric_id: 0,
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
                error={fabricsResource.message}
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
                                            fabric.balance?.available_meters ?? '0',
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
                                        {fabric.cost_per_kg
                                            ? `${compactDecimal(fabric.cost_per_kg)} ₽/кг`
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
                                                    cost_per_kg:
                                                        fabric.cost_per_kg
                                                            ? compactDecimal(
                                                                  fabric.cost_per_kg,
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
            {fabricsResource.message&&<button type="button" onClick={()=>void fabricsResource.retry()}>Обновить список тканей</button>}
            {fabricsResource.hasMore&&<button type="button" className={styles.secondaryButton} disabled={fabricsResource.loadingMore} onClick={()=>void fabricsResource.loadMore()}>Ещё ткани</button>}
            <section className={styles.relatedSection}>
                <h4>Расход ткани по моделям</h4>
                {requirementsResource.message && (
                    <p className={styles.error}>{requirementsResource.message}</p>
                )}
                <div className={styles.relationshipList}>
                    {requirementsResource.items.map((item) => (
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
                                <strong>{item.garment_model_name}</strong>
                                <small>{item.fabric_name}</small>
                            </span>
                            <span>
                                {compactDecimal(item.meters_per_unit)} м +{' '}
                                {compactDecimal(item.waste_percent)}%
                            </span>
                        </button>
                    ))}
                </div>
                {requirementsResource.message&&<button type="button" onClick={()=>void requirementsResource.retry()}>Обновить расходы ткани</button>}
                {requirementsResource.hasMore&&<button type="button" disabled={requirementsResource.loadingMore} onClick={()=>void requirementsResource.loadMore()}>Ещё расходы ткани</button>}
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
                                    ['cost_per_kg', 'Цена за кг', 'number'],
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
                                        step={type === 'number' ? field === 'minimum_stock_meters' ? '0.001' : '0.01' : undefined}
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
                            <ReferencePicker kind="models" value={requirementEditor.garment_model_id} onChange={garment_model_id=>setRequirementEditor({...requirementEditor,garment_model_id})}/>
                            <ReferencePicker kind="fabrics" value={requirementEditor.fabric_id} onChange={fabric_id=>setRequirementEditor({...requirementEditor,fabric_id})}/>
                            <label>
                                Метров на изделие
                                <input
                                    required
                                    type="number"
                                min="0.001"
                                step="0.001"
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
