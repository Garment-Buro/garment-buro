'use client';
import { useState } from 'react';
import type { SendCommand, Station, Unit } from '@/lib/production/types';
import styles from './ProductionTerminal.module.css';

export function UnitHandoff({
    unit,
    station,
    send,
    busy,
}: {
    unit: Unit;
    station: Station;
    send: SendCommand;
    busy: boolean;
}) {
    const [checks, setChecks] = useState<number[]>([]);
    const [due, setDue] = useState('');
    const [now] = useState(() => Date.now());
    const quality = unit.specification?.quality_checks ?? [];
    return (
        <section className={styles.section}>
            {unit.requires_dtf && (
                <p>
                    DTF:{' '}
                    {unit.dtf_ready
                        ? 'Доставлено — можно вложить в мешок изделия'
                        : 'Ожидается доставка'}
                    {unit.dtf_due_at && (
                        <strong>
                            {' '}
                            · Срок:{' '}
                            {new Date(unit.dtf_due_at).toLocaleString('ru-RU')}
                            {!unit.dtf_ready &&
                            new Date(unit.dtf_due_at).getTime() < now
                                ? ' · Просрочено'
                                : ''}
                        </strong>
                    )}
                </p>
            )}
            {station === 'cut' &&
                !unit.public_token &&
                ['cut', 'kit', 'waiting_dtf'].includes(unit.lane ?? '') && (
                    <button
                        disabled={busy}
                        onClick={() =>
                            void send({
                                action: 'issue_unit_label',
                                unit_id: unit.id,
                            })
                        }
                    >
                        Выпустить QR мешка изделия
                    </button>
                )}
            {station === 'kit' &&
                ['kit', 'waiting_dtf'].includes(unit.lane ?? '') && (
                    <>
                        {unit.requires_dtf &&
                            unit.dtf_ready &&
                            !unit.dtf_inserted && (
                                <button
                                    disabled={busy}
                                    onClick={() =>
                                        void send({
                                            action: 'insert_dtf',
                                            unit_id: unit.id,
                                        })
                                    }
                                >
                                    Наклейка получена и вложена в этот мешок
                                </button>
                            )}
                        <button
                            className={styles.primary}
                            disabled={
                                busy ||
                                !!unit.issue ||
                                Boolean(
                                    unit.requires_dtf && !unit.dtf_inserted,
                                ) ||
                                !unit.specification?.components.every(
                                    (c) => unit.checks[c.key],
                                )
                            }
                            onClick={() =>
                                void send({
                                    action: 'send_unit',
                                    unit_id: unit.id,
                                })
                            }
                        >
                            Мешок изделия собран — передать в цех
                        </button>
                    </>
                )}
            {station === 'dtf' &&
                unit.requires_dtf &&
                !unit.dtf_ready &&
                ['kit', 'waiting_dtf'].includes(unit.lane ?? '') && (
                    <>
                        <label>
                            Срок доставки наклейки
                            <input
                                type="datetime-local"
                                value={due}
                                onChange={(e) => setDue(e.target.value)}
                            />
                        </label>
                        <button
                            disabled={busy || !due}
                            onClick={() =>
                                void send({
                                    action: 'set_dtf_deadline',
                                    unit_id: unit.id,
                                    due_at: new Date(due).toISOString(),
                                })
                            }
                        >
                            Сохранить срок
                        </button>
                        <button
                            className={styles.primary}
                            disabled={busy || !!unit.issue}
                            onClick={() =>
                                void send({
                                    action: 'dtf_ready',
                                    unit_id: unit.id,
                                })
                            }
                        >
                            Наклейка изготовлена и доставлена
                        </button>
                    </>
                )}
            {station === 'workshop' && unit.lane === 'workshop' && (
                <>
                    <p>
                        Общий цех: нанесение, пошив и ВТО. Перед передачей
                        упаковщику проверьте изделие.
                    </p>
                    {quality.map((text, i) => (
                        <label className={styles.check} key={i}>
                            <input
                                type="checkbox"
                                checked={checks.includes(i)}
                                onChange={(e) =>
                                    setChecks((old) =>
                                        e.target.checked
                                            ? [...old, i]
                                            : old.filter((x) => x !== i),
                                    )
                                }
                            />
                            {text}
                        </label>
                    ))}
                    <button
                        className={styles.primary}
                        disabled={
                            busy ||
                            !!unit.issue ||
                            checks.length !== quality.length
                        }
                        onClick={() =>
                            void send({
                                action: 'complete_workshop',
                                unit_id: unit.id,
                                quality_confirmed: checks,
                            })
                        }
                    >
                        Цех и ВТО завершены — передать упаковщику
                    </button>
                </>
            )}
        </section>
    );
}
