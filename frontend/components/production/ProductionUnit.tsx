/* eslint-disable @next/next/no-img-element -- generated production QR */
'use client';
import { useRef, useState } from 'react';
import { PiPrinter, PiQrCode } from 'react-icons/pi';
import {
    labels,
    type Project,
    type SendCommand,
    type Station,
    type Unit,
} from '@/lib/production/types';
import { canAct, currentStage, visibleInstructions } from '@/lib/production/workflow';
import { productionApi } from '@/lib/api/production';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import { ProductionViews } from './workspaces/ProductionViews';
import { TechCardContent } from './workspaces/ProductionTechCard';
import { SpecificationForm } from './SpecificationForm';
import { OrderEvidence } from './OrderEvidence';
import { UnitHandoff } from './UnitHandoff';
import { ProductionCuttingBrief } from './ProductionCuttingBrief';
import styles from './ProductionTerminal.module.css';
import type { PrintTarget } from './PrintSheet';

export function ProductionUnit({
    unit,
    project,
    stations,
    station,
    send,
    busy,
    print,
}: {
    unit: Unit;
    project: Project;
    stations: Station[];
    station: Station;
    send: SendCommand;
    busy: boolean;
    print?: (target: PrintTarget) => void;
}) {
    const patternsDialog = useRef<HTMLDialogElement>(null);
    const cardDialog = useRef<HTMLDialogElement>(null);
    const run = useProductionAuthStore((state) => state.runAuthenticated);
    const [quality, setQuality] = useState<number[]>([]);
    const [note, setNote] = useState('');
    const [wrapped, setWrapped] = useState(false);
    const [error, setError] = useState('');
    const [downloading, setDownloading] = useState<Set<number>>(new Set());
    const stage =
            project.flow_version === 2 && unit.lane === 'cut'
                ? 'cut'
                : currentStage(unit),
        spec = unit.specification,
        tech = stations.includes('tech');
    const unitQr = unit.public_token
        ? `/api/qr-code?surface=production&size=256&path=${encodeURIComponent(`/production/label?token=${unit.public_token}`)}`
        : null;
    const download = async (id: number) => {
        setDownloading(current => new Set(current).add(id));
        setError('');
        try {
            const file = await run((token) =>
                productionApi.download(token, id, station, true),
            );
            const link = document.createElement('a');
            link.href = file.url;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            link.click();
        } catch (error) {
            setError(
                error instanceof Error ? error.message : 'Файл недоступен',
            );
        } finally {
            setDownloading(current => { const next = new Set(current); next.delete(id); return next; });
        }
    };
    return (
        <article className={styles.unit} id={`unit-${unit.id}`}>
            <div className={styles.row}>
                <span className={styles.number}>
                    {String(unit.number).padStart(2, '0')}
                </span>
                <div className={styles.grow}>
                    <h3>{unit.source.title}</h3>
                    <p className={styles.muted}>
                        {unit.source.size} · {unit.source.color} · вещь #
                        {unit.id}
                    </p>
                </div>
                <span
                    className={unit.issue ? styles.dangerBadge : styles.badge}
                >
                    {stage ? labels[stage] : spec ? 'Готово' : 'Нет задания'}
                </span>
            </div>
            {station !== 'tech' && <OrderEvidence unit={unit} />}
            {station === 'cut' && <ProductionCuttingBrief unit={unit} />}
            {project.flow_version === 2 && (
                <UnitHandoff
                    unit={unit}
                    station={station}
                    send={send}
                    busy={busy}
                />
            )}
            {unit.blockers.length > 0 && (
                <div className={styles.warning}>
                    {unit.blockers.map((text) => (
                        <p key={text}>{text}</p>
                    ))}
                </div>
            )}
            {station === 'tech' && (
                <>
                    <div className={styles.orderInfo}>
                        <p data-tone="blue">Размер<strong>{unit.source.size}</strong></p>
                        <p data-tone="purple">Цвет<strong>{unit.source.color}</strong></p>
                        <p data-tone="yellow">Нанесение<strong>{!spec ? 'Не задано' : spec.print_file_ids.length ? 'DTF' : 'Без нанесения'}</strong></p>
                        <button type="button" data-tone="blue" onClick={() => patternsDialog.current?.showModal()}>
                            Оригиналы лекал
                            <strong>{spec?.pattern_file_ids.length ? `${spec.pattern_file_ids.length} файл(а)` : 'Не прикреплены'}</strong>
                            <small>Открыть список файлов</small>
                        </button>
                        <button type="button" data-tone="purple" onClick={() => cardDialog.current?.showModal()}>
                            Техкарта
                            <strong>{unit.tech_card?.name || unit.cards.find(card => card.id === spec?.tech_card_revision_id)?.name || 'Техкарта не закреплена'}</strong>
                            <small>Просмотреть техкарту модели</small>
                        </button>
                    </div>
                    <dialog ref={cardDialog} className={styles.techCardDialog} aria-label="Техкарта изделия">
                        <header><h2>Техкарта изделия</h2><button type="button" onClick={() => cardDialog.current?.close()} aria-label="Закрыть техкарту">Закрыть</button></header>
                        <p>{unit.source.title} · {unit.source.size} · {unit.source.color}</p>
                        <TechCardContent unit={unit} />
                        {tech && project.state === 'inbox' && (
                            <details className={styles.section}>
                                <summary>{spec ? 'Изменить задание на эту вещь' : 'Подготовить задание на эту вещь'}</summary>
                                <SpecificationForm unit={unit} send={send} busy={busy} />
                            </details>
                        )}
                    </dialog>
                    <dialog ref={patternsDialog} className={styles.techCardDialog} aria-label="Оригиналы лекал">
                        <header><h2>Оригиналы лекал</h2><button type="button" onClick={() => patternsDialog.current?.close()}>Закрыть</button></header>
                        <p>{unit.source.title} · {unit.source.size} · вещь #{unit.id}</p>
                        {spec?.pattern_file_ids.length ? unit.files.filter(file => spec.pattern_file_ids.includes(file.id)).map(file => (
                            <div className={styles.file} key={file.id}>
                                <span>{file.name}<small>{Math.ceil(file.size_bytes / 1024)} КБ</small></span>
                                <button type="button" disabled={downloading.has(file.id)} onClick={() => void download(file.id)}>
                                    {downloading.has(file.id) ? 'Открываем…' : 'Открыть оригинал лекала'}
                                </button>
                            </div>
                        )) : <p>Лекала ещё не прикреплены к заданию на эту вещь.</p>}
                        {error && <p className={styles.error} role="alert">{error}</p>}
                    </dialog>
                </>
            )}
            {spec && (
                <>
                    <ol className={styles.route}>
                        {spec.route.map((step, index) => (
                            <li
                                key={step}
                                data-state={
                                    index < unit.stage_index
                                        ? 'done'
                                        : index === unit.stage_index
                                          ? 'active'
                                          : 'next'
                                }
                            >
                                {index < unit.stage_index ? '✓ ' : ''}
                                {labels[step]}
                            </li>
                        ))}
                    </ol>
                    {visibleInstructions(spec.instructions) && (
                        <p className={styles.instructions}>{visibleInstructions(spec.instructions)}</p>
                    )}
                    {canAct(stations, 'kit') && (
                        <details className={styles.section} open>
                            <summary>Комплектующие</summary>
                            {spec.components.map((component) => (
                                <label
                                    className={styles.component}
                                    key={component.key}
                                >
                                    <input
                                        type="checkbox"
                                        checked={Boolean(
                                            unit.checks[component.key],
                                        )}
                                        disabled={
                                            busy ||
                                            (project.flow_version === 2
                                                ? ![
                                                      'kit',
                                                      'waiting_dtf',
                                                  ].includes(unit.lane ?? '')
                                                : project.state !== 'kitting')
                                        }
                                        onChange={(event) =>
                                            void send({
                                                action: 'check_component',
                                                unit_id: unit.id,
                                                component_key: component.key,
                                                checked: event.target.checked,
                                            })
                                        }
                                    />
                                    <span>
                                        <strong>{component.name}</strong>
                                        <small>{component.location}</small>
                                    </span>
                                    <span>
                                        {component.quantity} {component.unit}
                                    </span>
                                </label>
                            ))}
                        </details>
                    )}
                    {spec.print_file_ids.length > 0 && (
                        <div className={styles.statusGrid}>
                            <p data-tone={unit.dtf_ready ? 'green' : 'yellow'}>
                                DTF у печатника
                                <strong>
                                    {unit.dtf_ready ? 'Готов' : 'Ожидается'}
                                </strong>
                            </p>
                            <p data-tone={unit.dtf_inserted ? 'green' : 'yellow'}>
                                DTF в мешке
                                <strong>
                                    {unit.dtf_inserted
                                        ? 'Вложен'
                                        : 'Не подтверждён'}
                                </strong>
                            </p>
                        </div>
                    )}
                    {!tech &&
                        (canAct(stations, 'cut') ||
                            canAct(stations, 'workshop') ||
                            canAct(stations, 'dtf') ||
                            canAct(stations, 'application')) && (
                            <details className={styles.section}>
                                <summary>Закреплённые оригиналы</summary>
                                {unit.files
                                    .filter(
                                        (file) =>
                                            tech ||
                                            (spec.pattern_file_ids.includes(
                                                file.id,
                                            ) &&
                                                (canAct(stations, 'cut') ||
                                                    canAct(
                                                        stations,
                                                        'workshop',
                                                    ))) ||
                                            (spec.print_file_ids.includes(
                                                file.id,
                                            ) &&
                                                (canAct(stations, 'dtf') ||
                                                    canAct(
                                                        stations,
                                                        'workshop',
                                                    ) ||
                                                    canAct(
                                                        stations,
                                                        'application',
                                                    ))),
                                    )
                                    .map((file) => (
                                        <div
                                            key={file.id}
                                            className={styles.file}
                                        >
                                            <span>
                                                {file.name}
                                                <small>
                                                    {spec.pattern_file_ids.includes(
                                                        file.id,
                                                    )
                                                        ? 'Лекала'
                                                        : 'Печать'}{' '}
                                                    · SHA256{' '}
                                                    {file.sha256.slice(0, 12)}…
                                                </small>
                                            </span>
                                            <button
                                                disabled={downloading.has(file.id)}
                                                onClick={() =>
                                                    void download(file.id)
                                                }
                                            >
                                                Открыть оригинал
                                            </button>
                                        </div>
                                    ))}
                            </details>
                        )}
                    {station === 'tech' && <ProductionViews unit={unit} station={station} />}
                    <div className={styles.actions}>
                        {tech &&
                            project.state === 'inbox' &&
                            !unit.documents_confirmed && (
                                <button
                                    disabled={busy}
                                    onClick={() =>
                                        void send({
                                            action: 'confirm_documents',
                                            unit_id: unit.id,
                                        })
                                    }
                                >
                                    Техкарта и лекала проверены
                                </button>
                            )}
                        {project.flow_version !== 2 &&
                            ['kitting', 'workshop', 'waiting_dtf'].includes(
                                project.state,
                            ) &&
                            spec.print_file_ids.length > 0 &&
                            !unit.dtf_ready &&
                            canAct(stations, 'dtf') && (
                                <button
                                    disabled={busy || !!unit.issue}
                                    onClick={() =>
                                        void send({
                                            action: 'dtf_ready',
                                            unit_id: unit.id,
                                        })
                                    }
                                >
                                    DTF напечатан, нарезан и подписан
                                </button>
                            )}
                        {project.flow_version !== 2 &&
                            ['kitting', 'waiting_dtf'].includes(
                                project.state,
                            ) &&
                            unit.dtf_ready &&
                            !unit.dtf_inserted &&
                            canAct(stations, 'kit') && (
                                <button
                                    disabled={busy || !!unit.issue}
                                    onClick={() =>
                                        void send({
                                            action: 'insert_dtf',
                                            unit_id: unit.id,
                                        })
                                    }
                                >
                                    Подтвердить: DTF вложен в мешок
                                </button>
                            )}
                    </div>
                    {project.state === 'workshop' &&
                        stage &&
                        (project.flow_version !== 2 || unit.lane === stage) &&
                        canAct(stations, stage) && (
                            <div className={styles.section}>
                                {stage === 'qc' &&
                                    spec.quality_checks.map((check, index) => (
                                        <label
                                            key={index}
                                            className={styles.check}
                                        >
                                            <input
                                                type="checkbox"
                                                checked={quality.includes(
                                                    index,
                                                )}
                                                onChange={(event) =>
                                                    setQuality((old) =>
                                                        event.target.checked
                                                            ? [...old, index]
                                                            : old.filter(
                                                                  (x) =>
                                                                      x !==
                                                                      index,
                                                              ),
                                                    )
                                                }
                                            />
                                            {check}
                                        </label>
                                    ))}
                                {stage === 'cut' && (
                                    <label className={styles.check}>
                                        <input
                                            type="checkbox"
                                            checked={wrapped}
                                            onChange={(event) =>
                                                setWrapped(event.target.checked)
                                            }
                                        />
                                        Крой завёрнут в подготовленный лист с QR
                                        вещи
                                    </label>
                                )}
                                <button
                                    className={styles.primary}
                                    disabled={
                                        busy ||
                                        !!unit.issue ||
                                        (stage === 'application' &&
                                            !unit.dtf_inserted) ||
                                        (stage === 'qc' &&
                                            quality.length !==
                                                spec.quality_checks.length) ||
                                        (stage === 'cut' && !wrapped)
                                    }
                                    onClick={() =>
                                        void send({
                                            action: 'complete_stage',
                                            unit_id: unit.id,
                                            stage,
                                            quality_confirmed: quality,
                                            ...(stage === 'cut'
                                                ? {
                                                      note: 'Крой завёрнут в лист с QR вещи',
                                                  }
                                                : {}),
                                        })
                                    }
                                >
                                    Завершить: {labels[stage]}
                                </button>
                                {stage === 'application' &&
                                    !unit.dtf_inserted && (
                                        <p className={styles.muted}>
                                            Комплектовщик должен подтвердить
                                            вложение DTF. До этого нанесение и
                                            дальнейший пошив недоступны.
                                        </p>
                                    )}
                            </div>
                        )}
                </>
            )}
            {station === 'tech' && !spec && <ProductionViews unit={unit} station={station} />}
                    {tech && (
                        <section className={styles.unitQrCard} data-ready={Boolean(unit.documents_confirmed && unitQr)}>
                            <div>
                                <PiQrCode aria-hidden />
                                <span>
                                    <strong>{unit.documents_confirmed && unitQr ? 'QR изделия готов' : 'Ожидает подтверждения техкарты и лекал'}</strong>
                                    <small>
                                        Вещь №{unit.id} · заказ №
                                        {project.order_id}
                                    </small>
                                </span>
                            </div>
                            {unit.documents_confirmed && unitQr && <img
                                src={unitQr}
                                alt={`QR изделия ${unit.id}`}
                                width={112}
                                height={112}
                            />}
                            {print && unit.documents_confirmed && unitQr && (
                                <button
                                    type="button"
                                    disabled={busy}
                                    onClick={() => print(unit.id)}
                                >
                                    <PiPrinter aria-hidden />
                                    Распечатать QR изделия
                                </button>
                            )}
                        </section>
                    )}
            {project.state !== 'dispatched' && station !== 'tech' && (
                <details className={styles.section}>
                    <summary>
                        {unit.issue ? 'Решение проблемы' : 'Проблема'}
                    </summary>
                    <label>
                        Описание
                        <textarea
                            rows={2}
                            maxLength={1000}
                            value={note}
                            onChange={(event) => setNote(event.target.value)}
                        />
                    </label>
                    <div className={styles.actions}>
                        {!unit.issue && (
                            <button
                                disabled={busy || !note.trim()}
                                onClick={() =>
                                    void send({
                                        action: 'report_issue',
                                        unit_id: unit.id,
                                        note,
                                    })
                                }
                            >
                                Отправить тикет администратору
                            </button>
                        )}
                        {unit.issue && (
                            <p className={styles.muted}>
                                Проблема передана администратору. Работа по
                                изделию возобновится после его решения.
                            </p>
                        )}
                    </div>
                </details>
            )}
            {error && (
                <p className={styles.error} role="alert">
                    {error}
                </p>
            )}
        </article>
    );
}
