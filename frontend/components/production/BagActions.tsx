'use client';
import { useState } from 'react';
import type { Project, SendCommand, Station } from '@/lib/production/types';
import { canAct } from '@/lib/production/workflow';
import { bagCanMove } from '@/lib/production/workspaces';
import { productionApi } from '@/lib/api/production';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import { PiPrinter } from 'react-icons/pi';
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
        [note, setNote] = useState(''),
        [waybillBusy, setWaybillBusy] = useState(false),
        [waybillError, setWaybillError] = useState('');
    const run = useProductionAuthStore((state) => state.runAuthenticated);
    const printWaybill = async () => {
        setWaybillBusy(true);
        setWaybillError('');
        try {
            const blob = await run((token) =>
                productionApi.cdekWaybill(token, project.project_id),
            );
            const url = URL.createObjectURL(blob);
            const frame = document.createElement('iframe');
            frame.hidden = true;
            frame.src = url;
            frame.onload = () => {
                frame.contentWindow?.print();
                window.setTimeout(() => {
                    URL.revokeObjectURL(url);
                    frame.remove();
                }, 60_000);
            };
            document.body.append(frame);
        } catch (error) {
            setWaybillError(
                error instanceof Error
                    ? error.message
                    : 'Не удалось подготовить накладную СДЭК',
            );
        } finally {
            setWaybillBusy(false);
        }
    };
    const reviewReady = project.units.every(
        (unit) =>
            unit.specification &&
            unit.documents_confirmed &&
            !unit.issue &&
            !unit.blockers.length,
    );
    return (
        <section className={styles.section}>
            {project.state === 'inbox' &&
                (canAct(stations, 'tech') || canAct(stations, 'dtf')) && (
                    <div className={styles.approvalPanel}>
                        <h3>Приёмка заказа</h3>
                        <p>
                            QR откроется только после независимого подтверждения
                            технолога и DTF.
                        </p>
                        <div className={styles.approvalGrid}>
                            <span data-ready={project.tech_approved}>
                                Технолог
                                <strong>
                                    {project.tech_approved
                                        ? 'Подтверждено'
                                        : 'Ожидается'}
                                </strong>
                            </span>
                            <span data-ready={project.dtf_approved}>
                                DTF
                                <strong>
                                    {project.dtf_approved
                                        ? 'Подтверждено'
                                        : 'Ожидается'}
                                </strong>
                            </span>
                            <span data-ready={project.qr_ready}>
                                QR заказа
                                <strong>
                                    {project.qr_ready
                                        ? 'Доступен'
                                        : 'Заблокирован'}
                                </strong>
                            </span>
                        </div>
                        <div className={styles.actions}>
                                {canAct(stations, 'tech') &&
                                    !project.tech_approved && (
                                        <button
                                            className={styles.primary}
                                            disabled={busy || !reviewReady}
                                            onClick={() =>
                                                void send({
                                                    action: 'approve_order',
                                                })
                                            }
                                        >
                                            Всё проверено — подтвердить технологом
                                        </button>
                                    )}
                                {canAct(stations, 'dtf') &&
                                    !project.dtf_approved && (
                                        <button
                                            className={styles.primary}
                                            disabled={busy || !reviewReady}
                                            onClick={() =>
                                                void send({
                                                    action: 'approve_order',
                                                })
                                            }
                                        >
                                            Макеты DTF проверены — подтвердить
                                        </button>
                                    )}
                        </div>
                    </div>
                )}
            <h3>Перемещение всего мешка</h3>
            <div className={styles.actions}>
                {project.state === 'inbox' && canAct(stations, 'tech') && (
                    <button
                        className={styles.primary}
                        disabled={
                            busy ||
                            !project.qr_ready ||
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
                            ? 'QR напечатан — передать закройщику'
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
                <details open={canAct(stations, 'packing')}>
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
            {canAct(stations, 'packing') && project.delivery && (
                <div className={styles.actions}>
                    <button
                        type="button"
                        disabled={busy || waybillBusy || project.is_demo}
                        onClick={() => void printWaybill()}
                    >
                        <PiPrinter aria-hidden="true" />
                        {waybillBusy
                            ? 'Готовим накладную…'
                            : 'Печать накладной СДЭК'}
                    </button>
                    {waybillError && (
                        <p className={styles.error} role="alert">
                            {waybillError}
                        </p>
                    )}
                </div>
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
