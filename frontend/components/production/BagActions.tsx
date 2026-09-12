'use client';
import { useState } from 'react';
import type { Project, SendCommand, Station } from '@/lib/production/types';
import { canAct } from '@/lib/production/workflow';
import { bagCanMove } from '@/lib/production/workspaces';
import styles from './ProductionTerminal.module.css';
export function BagActions({
    project,
    stations,
    send,
    busy,
}: {
    project: Project;
    stations: Station[];
    send: SendCommand;
    busy: boolean;
}) {
    const [tracking, setTracking] = useState(''),
        [note, setNote] = useState('');
    return (
        <section className={styles.section}>
            <h3>Перемещение всего мешка</h3>
            <div className={styles.actions}>
                {project.state === 'inbox' && canAct(stations, 'tech') && (
                    <button
                        className={styles.primary}
                        disabled={
                            busy ||
                            !project.units.every(
                                (x) =>
                                    x.specification &&
                                    x.documents_confirmed &&
                                    !x.blockers.length,
                            )
                        }
                        onClick={() => void send({ action: 'release' })}
                    >
                        {project.flow_version === 2
                            ? 'Подтвердить и передать закройщику'
                            : 'Передать на комплектовку'}
                    </button>
                )}
                {['kitting', 'waiting_dtf'].includes(project.state) &&
                    canAct(stations, 'kit') && (
                        <button
                            className={styles.primary}
                            disabled={busy || !bagCanMove(project)}
                            onClick={() => void send({ action: 'send_bag' })}
                        >
                            Мешок проверен — передать в цех
                        </button>
                    )}
                {project.flow_version !== 2 &&
                    project.state === 'workshop' &&
                    canAct(stations, 'kit') && (
                        <button
                            disabled={busy}
                            onClick={() =>
                                void send({ action: 'return_to_dtf' })
                            }
                        >
                            Вернуть весь мешок на стол ожидания DTF
                        </button>
                    )}
                {project.state === 'workshop' &&
                    canAct(stations, 'packing') && (
                        <button
                            className={styles.primary}
                            disabled={
                                busy ||
                                !project.units.every(
                                    (x) =>
                                        x.specification &&
                                        x.stage_index ===
                                            x.specification.route.length &&
                                        !x.issue,
                                )
                            }
                            onClick={() => void send({ action: 'pack_bag' })}
                        >
                            Все вещи вложены — закрыть упаковку
                        </button>
                    )}
            </div>
            {project.state === 'waiting_dtf' && (
                <p>
                    Подтвердите вложение плёнки для каждой ожидающей вещи, затем
                    верните весь мешок в цех.
                </p>
            )}
            {project.delivery && (
                <details>
                    <summary>Получатель и доставка</summary>
                    <p>
                        {project.delivery.recipient} · {project.delivery.phone}
                    </p>
                    <p>
                        {project.delivery.city} ·{' '}
                        {project.delivery.address ||
                            `ПВЗ ${project.delivery.point_code || 'не указан'}`}
                    </p>
                </details>
            )}
            {project.state === 'packed' && canAct(stations, 'shipping') && (
                <form
                    onSubmit={(event) => {
                        event.preventDefault();
                        void send({
                            action: 'dispatch',
                            tracking_number: tracking,
                            note,
                        });
                    }}
                >
                    <p>
                        Подтверждайте отправку только после передачи
                        перевозчику. Эта кнопка не создаёт заявку СДЭК.
                    </p>
                    <label>
                        Трек-номер
                        <input
                            required
                            minLength={3}
                            maxLength={100}
                            value={tracking}
                            onChange={(event) =>
                                setTracking(event.target.value)
                            }
                        />
                    </label>
                    <label>
                        Подтверждение передачи
                        <textarea
                            required
                            maxLength={1000}
                            value={note}
                            onChange={(event) => setNote(event.target.value)}
                            placeholder="Кому и когда передан заказ"
                        />
                    </label>
                    <button
                        className={styles.primary}
                        type="submit"
                        disabled={busy}
                    >
                        Зафиксировать отправку
                    </button>
                </form>
            )}
            {project.tracking_number && (
                <p className={styles.success}>
                    Отправлен · {project.tracking_number}
                </p>
            )}
        </section>
    );
}
