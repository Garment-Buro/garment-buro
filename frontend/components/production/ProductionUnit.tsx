'use client';
import { useState } from 'react';
import {
    labels,
    type Project,
    type SendCommand,
    type Stage,
    type Station,
    type Unit,
} from '@/lib/production/types';
import { canAct, currentStage } from '@/lib/production/workflow';
import { productionApi } from '@/lib/api/production';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import { SpecificationForm } from './SpecificationForm';
import { OrderEvidence } from './OrderEvidence';
import { UnitHandoff } from './UnitHandoff';
import styles from './ProductionTerminal.module.css';

export function ProductionUnit({
    unit,
    project,
    stations,
    station,
    send,
    busy,
}: {
    unit: Unit;
    project: Project;
    stations: Station[];
    station: Station;
    send: SendCommand;
    busy: boolean;
}) {
    const run = useProductionAuthStore((state) => state.runAuthenticated);
    const [quality, setQuality] = useState<number[]>([]);
    const [note, setNote] = useState('');
    const [wrapped, setWrapped] = useState(false);
    const [rework, setRework] = useState<Stage>(
        unit.specification?.route[0] ?? 'cut',
    );
    const [error, setError] = useState('');
    const [downloading, setDownloading] = useState(false);
    const stage =
            project.flow_version === 2 && unit.lane === 'cut'
                ? 'cut'
                : currentStage(unit),
        spec = unit.specification,
        tech = stations.includes('tech');
    const download = async (id: number) => {
        setDownloading(true);
        setError('');
        try {
            const file = await run((token) =>
                productionApi.download(token, id, station),
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
            setDownloading(false);
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
            <OrderEvidence unit={unit} />
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
            {tech && station === 'tech' && project.state === 'inbox' && (
                <SpecificationForm unit={unit} send={send} busy={busy} />
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
                    <p className={styles.instructions}>{spec.instructions}</p>
                    <details
                        className={styles.section}
                        open={station === 'kit'}
                    >
                        <summary>
                            Комплектность ·{' '}
                            {Object.values(unit.checks).filter(Boolean).length}/
                            {spec.components.length}
                        </summary>
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
                                            ? !['kit', 'waiting_dtf'].includes(
                                                  unit.lane ?? '',
                                              )
                                            : project.state !== 'kitting') ||
                                        !canAct(stations, 'kit')
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
                    {spec.print_file_ids.length > 0 && (
                        <div className={styles.statusGrid}>
                            <p>
                                DTF у печатника
                                <strong>
                                    {unit.dtf_ready ? 'Готов' : 'Ожидается'}
                                </strong>
                            </p>
                            <p>
                                DTF в мешке
                                <strong>
                                    {unit.dtf_inserted
                                        ? 'Вложен'
                                        : 'Не подтверждён'}
                                </strong>
                            </p>
                        </div>
                    )}
                    {(tech || canAct(stations, 'cut') ||
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
                                                canAct(stations, 'workshop') ||
                                                canAct(
                                                    stations,
                                                    'application',
                                                ))),
                                )
                                .map((file) => (
                                    <div key={file.id} className={styles.file}>
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
                                            disabled={downloading}
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
                        {unit.documents_confirmed &&
                            project.state === 'inbox' && (
                                <span className={styles.success}>
                                    Документы подтверждены технологом
                                </span>
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
            {!['packed', 'dispatched'].includes(project.state) &&
                project.version > 0 && (
                    <details className={styles.section}>
                        <summary>
                            {unit.issue
                                ? 'Решение проблемы'
                                : 'Сообщить о проблеме'}
                        </summary>
                        <label>
                            Описание
                            <textarea
                                rows={2}
                                maxLength={1000}
                                value={note}
                                onChange={(event) =>
                                    setNote(event.target.value)
                                }
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
                                    Остановить вещь и записать проблему
                                </button>
                            )}
                            {unit.issue && tech && (
                                <>
                                    <button
                                        disabled={busy || !note.trim()}
                                        onClick={() =>
                                            void send({
                                                action: 'resolve_issue',
                                                unit_id: unit.id,
                                                note,
                                            })
                                        }
                                    >
                                        Проблема устранена
                                    </button>
                                    {spec && (
                                        <>
                                            <label>
                                                Переделка с этапа
                                                <select
                                                    value={rework}
                                                    onChange={(event) =>
                                                        setRework(
                                                            event.target
                                                                .value as Stage,
                                                        )
                                                    }
                                                >
                                                    {spec.route
                                                        .slice(
                                                            0,
                                                            unit.stage_index +
                                                                1,
                                                        )
                                                        .map((step) => (
                                                            <option
                                                                key={step}
                                                                value={step}
                                                            >
                                                                {labels[step]}
                                                            </option>
                                                        ))}
                                                </select>
                                            </label>
                                            <button
                                                disabled={
                                                    busy ||
                                                    !note.trim() ||
                                                    !spec.route.includes(
                                                        rework,
                                                    ) ||
                                                    unit.crm_status ===
                                                        'completed'
                                                }
                                                onClick={() =>
                                                    void send({
                                                        action: 'rework',
                                                        unit_id: unit.id,
                                                        note,
                                                        stage: rework,
                                                    })
                                                }
                                            >
                                                Назначить переделку
                                            </button>
                                        </>
                                    )}
                                </>
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
