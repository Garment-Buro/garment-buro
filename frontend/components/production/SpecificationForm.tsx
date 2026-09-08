'use client';
import { useState } from 'react';
import {
    labels,
    stages,
    type Component,
    type SendCommand,
    type Specification,
    type Unit,
} from '@/lib/production/types';
import { productionApi } from '@/lib/api/production';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import styles from './ProductionTerminal.module.css';

export function SpecificationForm({
    unit,
    send,
    busy,
}: {
    unit: Unit;
    send: SendCommand;
    busy: boolean;
}) {
    const run = useProductionAuthStore((state) => state.runAuthenticated);
    const [value, setValue] = useState<Specification>(
        unit.specification
            ? {
                  tech_card_revision_id:
                      unit.specification.tech_card_revision_id,
                  garment_size_id: unit.specification.garment_size_id,
                  route: unit.specification.route,
                  components: unit.specification.components,
                  pattern_file_ids: unit.specification.pattern_file_ids,
                  print_file_ids: unit.specification.print_file_ids,
                  instructions: unit.specification.instructions,
                  quality_checks: unit.specification.quality_checks,
              }
            : {
                  tech_card_revision_id: unit.cards[0]?.id ?? 0,
                  garment_size_id:
                      unit.sizes.find((x) => x.code === unit.source.size)?.id ??
                      null,
                  route: [...stages],
                  components: [
                      {
                          key: 'component_1',
                          name: '',
                          quantity: '1',
                          unit: 'шт',
                          location: '',
                      },
                  ],
                  pattern_file_ids: [],
                  print_file_ids: [],
                  instructions: '',
                  quality_checks: [
                      'Размер и посадка соответствуют заказу',
                      'Качество швов, нанесений и комплектность',
                  ],
              },
    );
    const [uploading, setUploading] = useState(false);
    const [files, setFiles] = useState(unit.files);
    const [error, setError] = useState('');
    const change = (patch: Partial<Specification>) =>
        setValue((old) => ({ ...old, ...patch }));
    const component = (index: number, patch: Partial<Component>) =>
        change({
            components: value.components.map((x, i) =>
                i === index ? { ...x, ...patch } : x,
            ),
        });
    const chooseFile = (
        field: 'pattern_file_ids' | 'print_file_ids',
        id: number,
        checked: boolean,
    ) =>
        change({
            [field]: checked
                ? [...value[field], id]
                : value[field].filter((x) => x !== id),
        });
    const upload = async (file: File) => {
        setUploading(true);
        setError('');
        try {
            // Immutable, collision-safe slot; duplicate submissions are reconciled by the storage service.
            const saved = await run((token) =>
                productionApi.upload(
                    token,
                    unit.id,
                    Math.floor(Date.now() / 1000),
                    file,
                ),
            );
            setFiles((old) => [
                ...old.filter((x) => x.id !== saved.attachment_id),
                {
                    id: saved.attachment_id,
                    name: file.name,
                    card_id: null,
                    size_bytes: saved.size_bytes,
                    content_type: saved.content_type,
                    sha256: saved.checksum_sha256,
                },
            ]);
        } catch (error) {
            setError(
                error instanceof Error ? error.message : 'Файл не сохранён',
            );
        } finally {
            setUploading(false);
        }
    };
    return (
        <details className={styles.section} open={!unit.specification}>
            <summary>
                Спецификация технолога
                {unit.revision ? ` · версия ${unit.revision}` : ''}
            </summary>
            <form
                onSubmit={(event) => {
                    event.preventDefault();
                    void send({
                        action: 'plan',
                        unit_id: unit.id,
                        specification: value,
                    });
                }}
            >
                <p>
                    Сверьте конструкцию, мерки и все нанесения с заказом. После
                    выпуска в работу эта версия фиксируется.
                </p>
                <div className={styles.grid2}>
                    <label>
                        Опубликованная техкарта
                        <select
                            required
                            value={value.tech_card_revision_id || ''}
                            onChange={(event) =>
                                change({
                                    tech_card_revision_id: Number(
                                        event.target.value,
                                    ),
                                    pattern_file_ids: [],
                                })
                            }
                        >
                            <option value="" disabled>
                                Нет опубликованных техкарт
                            </option>
                            {unit.cards.map((card) => (
                                <option key={card.id} value={card.id}>
                                    {card.name} · v{card.revision}
                                </option>
                            ))}
                        </select>
                    </label>
                    <label>
                        Размер модели
                        <select
                            required
                            value={value.garment_size_id ?? ''}
                            onChange={(event) =>
                                change({
                                    garment_size_id: Number(event.target.value),
                                })
                            }
                        >
                            <option value="" disabled>
                                Выберите размер
                            </option>
                            {unit.sizes.map((size) => (
                                <option key={size.id} value={size.id}>
                                    {size.code}
                                </option>
                            ))}
                        </select>
                    </label>
                </div>
                <fieldset>
                    <legend>Маршрут вещи</legend>
                    <div className={styles.row}>
                        {stages.map((stage) => (
                            <label className={styles.check} key={stage}>
                                <input
                                    type="checkbox"
                                    checked={value.route.includes(stage)}
                                    disabled={
                                        stage === 'qc' || stage === 'packing'
                                    }
                                    onChange={(event) =>
                                        change({
                                            route: stages.filter((x) =>
                                                x === stage
                                                    ? event.target.checked
                                                    : value.route.includes(x),
                                            ),
                                        })
                                    }
                                />
                                {labels[stage]}
                            </label>
                        ))}
                    </div>
                </fieldset>
                <fieldset>
                    <legend>Комплектующие и места хранения</legend>
                    {value.components.map((item, index) => (
                        <div className={styles.componentForm} key={item.key}>
                            <label>
                                Наименование
                                <input
                                    required
                                    maxLength={160}
                                    value={item.name}
                                    onChange={(event) =>
                                        component(index, {
                                            name: event.target.value,
                                        })
                                    }
                                />
                            </label>
                            <label>
                                Количество
                                <input
                                    required
                                    type="number"
                                    min="0.001"
                                    step="0.001"
                                    value={item.quantity}
                                    onChange={(event) =>
                                        component(index, {
                                            quantity: event.target.value,
                                        })
                                    }
                                />
                            </label>
                            <label>
                                Единица
                                <select
                                    value={item.unit}
                                    onChange={(event) =>
                                        component(index, {
                                            unit: event.target
                                                .value as Component['unit'],
                                        })
                                    }
                                >
                                    {['шт', 'м', 'комплект'].map((x) => (
                                        <option key={x}>{x}</option>
                                    ))}
                                </select>
                            </label>
                            <label>
                                Ячейка / склад
                                <input
                                    required
                                    maxLength={160}
                                    value={item.location}
                                    onChange={(event) =>
                                        component(index, {
                                            location: event.target.value,
                                        })
                                    }
                                />
                            </label>
                            <button
                                type="button"
                                disabled={value.components.length === 1}
                                onClick={() =>
                                    change({
                                        components: value.components.filter(
                                            (_, i) => i !== index,
                                        ),
                                    })
                                }
                            >
                                Убрать
                            </button>
                        </div>
                    ))}
                    <button
                        type="button"
                        onClick={() =>
                            change({
                                components: [
                                    ...value.components,
                                    {
                                        key: crypto.randomUUID(),
                                        name: '',
                                        quantity: '1',
                                        unit: 'шт',
                                        location: '',
                                    },
                                ],
                            })
                        }
                    >
                        Добавить комплектующую
                    </button>
                </fieldset>
                <fieldset>
                    <legend>Оригиналы файлов</legend>
                    <p>
                        PDF, PNG, JPEG, WebP. Лекала и макеты печати — отдельные
                        файлы. После загрузки выберите назначение каждого файла.
                        Параметры формы сохранятся.
                    </p>
                    <label>
                        Загрузить файл
                        <input
                            type="file"
                            accept="application/pdf,image/png,image/jpeg,image/webp"
                            disabled={busy || uploading}
                            onChange={(event) => {
                                const file = event.target.files?.[0];
                                if (file) void upload(file);
                            }}
                        />
                    </label>
                    {uploading && (
                        <p role="status">
                            Сохраняем оригинал в приватное хранилище…
                        </p>
                    )}
                    {files
                        .filter(
                            (x) =>
                                !x.card_id ||
                                x.card_id === value.tech_card_revision_id,
                        )
                        .map((file) => (
                            <div className={styles.file} key={file.id}>
                                <span>
                                    {file.name}{' '}
                                    <small>
                                        · #{file.id} ·{' '}
                                        {Math.ceil(file.size_bytes / 1024)} КБ
                                    </small>
                                </span>
                                <label className={styles.check}>
                                    <input
                                        type="checkbox"
                                        checked={value.pattern_file_ids.includes(
                                            file.id,
                                        )}
                                        onChange={(event) =>
                                            chooseFile(
                                                'pattern_file_ids',
                                                file.id,
                                                event.target.checked,
                                            )
                                        }
                                    />
                                    Лекала
                                </label>
                                {!file.card_id && (
                                    <label className={styles.check}>
                                        <input
                                            type="checkbox"
                                            checked={value.print_file_ids.includes(
                                                file.id,
                                            )}
                                            onChange={(event) =>
                                                chooseFile(
                                                    'print_file_ids',
                                                    file.id,
                                                    event.target.checked,
                                                )
                                            }
                                        />
                                        DTF
                                    </label>
                                )}
                            </div>
                        ))}
                </fieldset>
                <label>
                    Технологические указания и параметры нанесений
                    <textarea
                        required
                        minLength={1}
                        maxLength={4000}
                        rows={4}
                        value={value.instructions}
                        onChange={(event) =>
                            change({ instructions: event.target.value })
                        }
                        placeholder="Материал, особенности сборки, соответствие файлов сторонам изделия, размеры и расположение каждого нанесения, режим переноса…"
                    />
                </label>
                <label>
                    Проверки ОТК — одна на строку
                    <textarea
                        required
                        rows={3}
                        value={value.quality_checks.join('\n')}
                        onChange={(event) =>
                            change({
                                quality_checks: event.target.value.split('\n'),
                            })
                        }
                    />
                </label>
                {error && (
                    <p className={styles.error} role="alert">
                        {error}
                    </p>
                )}
                <button
                    className={styles.primary}
                    disabled={busy || uploading || !value.tech_card_revision_id}
                    type="submit"
                >
                    Закрепить спецификацию и файлы
                </button>
            </form>
        </details>
    );
}
