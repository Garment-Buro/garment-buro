'use client';

import { useCallback, useState } from 'react';
import { PiCheck, PiPlus } from 'react-icons/pi';
import { useAssortmentResource } from '@/hooks/production/useAssortmentResource';
import { usePatternFiles } from '@/hooks/production/useReferenceDirectory';
import {
    readPatternCoverage,
    patternSlot,
    sleeveVariants,
    type PatternModelCard,
} from '@/lib/production/patternDirectory';
import {
    variantLabel,
    variantShortLabel,
} from '@/lib/production/patternEditor';
import { compactDecimal } from '@/lib/production/numbers';
import { ReferencePicker } from './ReferencePicker';
import type { PatternTarget } from './PatternEditor';
import { AssortmentFeedback } from './AssortmentDialog';
import styles from '../ProductionAdmin.module.css';

export function PatternCoveragePanel({
    model,
    revision,
    onOpen,
}: {
    model: PatternModelCard;
    revision: number;
    onOpen: (target: PatternTarget) => void;
}) {
    const [view, setView] = useState<'grid' | 'files'>('grid'),
        [selectingSize, setSelectingSize] = useState(false);
    const [window, setWindow] = useState<{
        sizeId: number;
        width: number;
        length: number;
        version?: number;
    }>({ sizeId: 0, width: 0, length: 0 });
    const params = new URLSearchParams({
        width_page: String(window.width),
        length_page: String(window.length),
    });
    if (window.sizeId) params.set('size_id', String(window.sizeId));
    if (window.version)
        params.set('expected_size_version', String(window.version));
    const decode = useCallback(
        (value: unknown) => {
            const row = readPatternCoverage(value);
            if (
                row.model.id !== model.id ||
                (window.sizeId && row.size?.id !== window.sizeId) ||
                row.width_page !== window.width ||
                row.length_page !== window.length
            )
                throw new Error('Сервер вернул участок другой сетки.');
            return row;
        },
        [model.id, window.sizeId, window.width, window.length],
    );
    const grid = useAssortmentResource(
        `models/${model.id}/pattern-coverage?${params}`,
        view === 'grid',
        decode,
        revision,
    );
    const data = grid.data,
        bySlot = new Map(
            data?.items.map((item) => [
                patternSlot(item.width_cm, item.length_cm, item.sleeve_variant),
                item,
            ]) ?? [],
        );
    const reset = () => {
        setWindow({ sizeId: 0, width: 0, length: 0 });
        grid.reload();
    };
    const move = (axis: 'width' | 'length', page: number) => {
        if (data?.size)
            setWindow({
                ...window,
                sizeId: data.size.id,
                [axis]: page,
                version: data.size.version,
            });
    };
    return (
        <div className={styles.patternSizeList}>
            <div className={styles.headingActions}>
                <button
                    type="button"
                    aria-pressed={view === 'grid'}
                    onClick={() => setView('grid')}
                >
                    Сетка размеров
                </button>
                <button
                    type="button"
                    aria-pressed={view === 'files'}
                    onClick={() => setView('files')}
                >
                    Все файлы модели
                </button>
            </div>
            {view === 'files' ? (
                <PatternFiles
                    modelId={model.id}
                    revision={revision}
                    onOpen={onOpen}
                />
            ) : (
                <>
                    {grid.loading && (
                        <p role="status">Загружаем участок сетки…</p>
                    )}
                    {grid.error && (
                        <p role="alert">
                            {grid.error}{' '}
                            <button type="button" onClick={reset}>
                                Обновить сетку
                            </button>
                        </p>
                    )}
                    {!grid.loading && !grid.error && data && (
                        <>
                            <div className={styles.patternSizeSummary}>
                                <div>
                                    <strong>
                                        {data.size
                                            ? `Размер ${data.size.code}`
                                            : 'У модели нет размеров'}
                                    </strong>
                                    <small>
                                        {data.size?.is_active === false
                                            ? 'Архивный размер'
                                            : 'Актуальная сетка'}
                                    </small>
                                </div>
                                <button
                                    type="button"
                                    onClick={() =>
                                        setSelectingSize((value) => !value)
                                    }
                                >
                                    Выбрать размер
                                </button>
                            </div>
                            {selectingSize && (
                                <ReferencePicker
                                    kind="pattern-sizes"
                                    modelId={model.id}
                                    value={data.size?.id ?? 0}
                                    onChange={(id) => {
                                        if (id) {
                                            setWindow({
                                                sizeId: id,
                                                width: 0,
                                                length: 0,
                                            });
                                            setSelectingSize(false);
                                        }
                                    }}
                                />
                            )}
                            {data.size && (
                                <>
                                    <p>
                                        {data.uploaded_count} из{' '}
                                        {BigInt(
                                            data.required_count,
                                        ).toLocaleString('ru-RU')}{' '}
                                        лекал загружено для размера.
                                    </p>
                                    {data.width_values.length &&
                                    data.length_values.length ? (
                                        <>
                                            <WindowPager
                                                key={`width:${data.width_page}`}
                                                label="Страница ширины"
                                                page={data.width_page}
                                                pages={data.width_pages}
                                                onChange={(page) =>
                                                    move('width', page)
                                                }
                                            />
                                            <WindowPager
                                                key={`length:${data.length_page}`}
                                                label="Страница длины"
                                                page={data.length_page}
                                                pages={data.length_pages}
                                                onChange={(page) =>
                                                    move('length', page)
                                                }
                                            />
                                            <div
                                                className={
                                                    styles.patternCoverageScroll
                                                }
                                                role="region"
                                                tabIndex={0}
                                                aria-label={`Сетка лекал ${model.name}, размер ${data.size.code}`}
                                            >
                                                <table
                                                    className={
                                                        styles.patternCoverageTable
                                                    }
                                                >
                                                    <thead>
                                                        <tr>
                                                            <th scope="col">
                                                                Длина ↓ / Ширина
                                                                →
                                                            </th>
                                                            {data.width_values.map(
                                                                (width) => (
                                                                    <th
                                                                        scope="col"
                                                                        key={
                                                                            width
                                                                        }
                                                                    >
                                                                        {compactDecimal(
                                                                            width,
                                                                        )}{' '}
                                                                        см
                                                                    </th>
                                                                ),
                                                            )}
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {data.length_values.map(
                                                            (length) => (
                                                                <tr
                                                                    key={length}
                                                                >
                                                                    <th scope="row">
                                                                        {compactDecimal(
                                                                            length,
                                                                        )}{' '}
                                                                        см
                                                                    </th>
                                                                    {data.width_values.map(
                                                                        (
                                                                            width,
                                                                        ) => (
                                                                            <td
                                                                                key={
                                                                                    width
                                                                                }
                                                                            >
                                                                                <div
                                                                                    className={
                                                                                        styles.patternSlot
                                                                                    }
                                                                                >
                                                                                    {sleeveVariants(
                                                                                        data.size!,
                                                                                    ).map(
                                                                                        (
                                                                                            variant,
                                                                                        ) => {
                                                                                            const pattern =
                                                                                                    bySlot.get(
                                                                                                        patternSlot(
                                                                                                            width,
                                                                                                            length,
                                                                                                            variant,
                                                                                                        ),
                                                                                                    ),
                                                                                                readonly =
                                                                                                    !data
                                                                                                        .model
                                                                                                        .is_active ||
                                                                                                    !data
                                                                                                        .size!
                                                                                                        .is_active;
                                                                                            return (
                                                                                                <button
                                                                                                    type="button"
                                                                                                    className={
                                                                                                        styles.patternVariantSlot
                                                                                                    }
                                                                                                    key={
                                                                                                        variant
                                                                                                    }
                                                                                                    data-state={
                                                                                                        pattern
                                                                                                            ? pattern.is_active
                                                                                                                ? 'ready'
                                                                                                                : 'hidden'
                                                                                                            : 'missing'
                                                                                                    }
                                                                                                    disabled={
                                                                                                        !pattern &&
                                                                                                        readonly
                                                                                                    }
                                                                                                    aria-label={`${variantLabel[variant]} · ${width} × ${length} см${pattern ? ' · ' + pattern.code : ' · файл не загружен'}`}
                                                                                                    onClick={() =>
                                                                                                        onOpen(
                                                                                                            pattern
                                                                                                                ? {
                                                                                                                      patternId:
                                                                                                                          pattern.id,
                                                                                                                  }
                                                                                                                : {
                                                                                                                      modelId:
                                                                                                                          model.id,
                                                                                                                      sizeId: data
                                                                                                                          .size!
                                                                                                                          .id,
                                                                                                                      point: {
                                                                                                                          width,
                                                                                                                          length,
                                                                                                                          variant,
                                                                                                                      },
                                                                                                                  },
                                                                                                        )
                                                                                                    }
                                                                                                >
                                                                                                    {pattern ? (
                                                                                                        <PiCheck
                                                                                                            aria-hidden
                                                                                                        />
                                                                                                    ) : (
                                                                                                        <PiPlus
                                                                                                            aria-hidden
                                                                                                        />
                                                                                                    )}
                                                                                                    <span>
                                                                                                        {
                                                                                                            variantShortLabel[
                                                                                                                variant
                                                                                                            ]
                                                                                                        }
                                                                                                    </span>
                                                                                                </button>
                                                                                            );
                                                                                        },
                                                                                    )}
                                                                                </div>
                                                                            </td>
                                                                        ),
                                                                    )}
                                                                </tr>
                                                            ),
                                                        )}
                                                    </tbody>
                                                </table>
                                            </div>
                                            <div
                                                className={
                                                    styles.patternSlotLegend
                                                }
                                            >
                                                <span data-state="ready">
                                                    Загружено
                                                </span>
                                                <span data-state="missing">
                                                    Не загружено
                                                </span>
                                                <span data-state="hidden">
                                                    Скрыто
                                                </span>
                                            </div>
                                        </>
                                    ) : (
                                        <p>
                                            В модели не заполнены диапазоны
                                            ширины и длины для этого размера.
                                            Сохранённые файлы доступны в разделе
                                            «Все файлы модели».
                                        </p>
                                    )}
                                </>
                            )}
                        </>
                    )}
                </>
            )}
        </div>
    );
}

function WindowPager({
    label,
    page,
    pages,
    onChange,
}: {
    label: string;
    page: number;
    pages: number;
    onChange: (page: number) => void;
}) {
    const [draft, setDraft] = useState(String(page + 1));
    if (pages <= 1) return null;
    const requested = Number(draft),
        valid =
            Number.isSafeInteger(requested) &&
            requested >= 1 &&
            requested <= pages;
    return (
        <div className={styles.patternPager}>
            <label>
                {label}
                <input
                    type="number"
                    min={1}
                    max={pages}
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                />
            </label>
            <small>из {pages}</small>
            <button
                type="button"
                disabled={page === 0}
                aria-label={`${label}: назад`}
                onClick={() => onChange(page - 1)}
            >
                Назад
            </button>
            <button
                type="button"
                disabled={page + 1 === pages}
                aria-label={`${label}: вперёд`}
                onClick={() => onChange(page + 1)}
            >
                Вперёд
            </button>
            <button
                type="button"
                disabled={!valid || requested === page + 1}
                aria-label={`${label}: перейти`}
                onClick={() => onChange(requested - 1)}
            >
                Перейти
            </button>
        </div>
    );
}

function PatternFiles({
    modelId,
    revision,
    onOpen,
}: {
    modelId: number;
    revision: number;
    onOpen: (target: PatternTarget) => void;
}) {
    const [query, setQuery] = useState('');
    const files = usePatternFiles(
        { model_id: modelId, query, limit: 24, sort: 'id:desc' },
        revision,
    );
    return (
        <section aria-label="Файлы лекал модели">
            <label>
                Поиск файла лекала
                <input
                    type="search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                />
            </label>
            <AssortmentFeedback
                loading={files.loading}
                error={files.message}
                empty={!files.loading && !files.items.length}
            />
            <div className={styles.relationshipList}>
                {files.items.map((item) => (
                    <button
                        type="button"
                        key={item.id}
                        className={styles.relationshipCard}
                        onClick={() => onOpen({ patternId: item.id })}
                        aria-label={`Изменить лекало ${item.code}`}
                    >
                        <span>
                            <strong>{item.code}</strong>
                            <small>{item.name}</small>
                            <small>
                                Размер {item.size_code}
                                {item.size_is_active
                                    ? ''
                                    : ' · архивный'} ·{' '}
                                {compactDecimal(item.width_cm)} ×{' '}
                                {compactDecimal(item.length_cm)} см
                            </small>
                        </span>
                        <span>
                            {variantShortLabel[item.sleeve_variant]} ·{' '}
                            {item.is_active ? 'Активно' : 'Скрыто'}
                        </span>
                    </button>
                ))}
            </div>
            {files.message && (
                <button type="button" onClick={() => void files.retry()}>
                    Обновить файлы лекал
                </button>
            )}
            {files.hasMore && (
                <button
                    type="button"
                    disabled={files.loadingMore}
                    onClick={() => void files.loadMore()}
                >
                    Ещё файлы лекал
                </button>
            )}
        </section>
    );
}
