'use client';
import { useState } from 'react';
import type { Project, SendCommand, Station } from '@/lib/production/types';
import { canAct } from '@/lib/production/workflow';
import { bagCanMove } from '@/lib/production/workspaces';
import { productionApi } from '@/lib/api/production';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import {
    PiCheckCircle,
    PiPrinter,
    PiQrCode,
    PiWarningCircle,
} from 'react-icons/pi';
import styles from './ProductionTerminal.module.css';
export function BagActions({
    project,
    stations,
    send,
    busy,
    print,
    printing = false,
}: {
    project: Project;
    stations: Station[];
    send: SendCommand;
    busy: boolean;
    print?: () => void;
    printing?: boolean;
}) {
    const [tracking, setTracking] = useState(''),
        [shippingNote, setShippingNote] = useState(''),
        [issueOpen, setIssueOpen] = useState(false),
        [issueNote, setIssueNote] = useState(''),
        [issueUnit, setIssueUnit] = useState(
            String(project.units.find((unit) => !unit.issue)?.id ?? ''),
        ),
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
    const isTechReview = project.state === 'inbox' && canAct(stations, 'tech');
    const isDtfReview = project.state === 'inbox' && canAct(stations, 'dtf');
    const isReview = isTechReview || isDtfReview;
    const availableIssueUnits = project.units.filter((unit) => !unit.issue);
    const reportIssue = async () => {
        if (!issueUnit || !issueNote.trim()) return;
        const saved = await send({
            action: 'report_issue',
            unit_id: Number(issueUnit),
            note: issueNote.trim(),
        });
        if (saved) {
            setIssueOpen(false);
            setIssueNote('');
        }
    };
    return (
        <section
            className={`${styles.section} ${isReview ? styles.intakeSection : ''}`}
        >
            {isReview && (
                <div className={styles.approvalPanel}>
                    <div className={styles.intakeHeading}>
                        <div>
                            <h3>Приёмка заказа</h3>
                            <p>Технолог и DTF подтверждают заказ независимо.</p>
                        </div>
                    </div>
                    <div className={styles.approvalGrid}>
                        <span data-ready={project.tech_approved}>
                            Технолог
                            <strong>
                                {project.tech_approved
                                    ? 'Подтверждение технолога получено'
                                    : 'Ждём подтверждение технолога'}
                            </strong>
                        </span>
                        <span data-ready={project.dtf_approved}>
                            DTF
                            <strong>
                                {project.dtf_approved
                                    ? 'Подтверждение DTF получено'
                                    : 'Ждём подтверждение DTF'}
                            </strong>
                        </span>
                    </div>
                    <div className={styles.intakeActions}>
                        {isTechReview && !project.tech_approved && (
                            <button
                                className={styles.primary}
                                disabled={busy || !reviewReady}
                                onClick={() =>
                                    void send({
                                        action: 'approve_order',
                                    })
                                }
                            >
                                <PiQrCode aria-hidden />
                                Подтвердить заказ
                            </button>
                        )}
                        {isTechReview &&
                            project.tech_approved &&
                            !project.qr_ready && (
                                <button type="button" disabled>
                                    <PiQrCode aria-hidden />
                                    Ждём подтверждение DTF
                                </button>
                            )}
                        {isTechReview && project.qr_ready && print && (
                            <button
                                type="button"
                                disabled={busy || printing}
                                onClick={print}
                            >
                                <PiPrinter aria-hidden />
                                {printing ? 'Готовим QR…' : 'Распечатать QR'}
                            </button>
                        )}
                        {isDtfReview && !project.dtf_approved && (
                            <button
                                className={styles.primary}
                                disabled={busy || !reviewReady}
                                onClick={() =>
                                    void send({
                                        action: 'approve_order',
                                    })
                                }
                            >
                                <PiCheckCircle aria-hidden />
                                Подтвердить DTF
                            </button>
                        )}
                        {isTechReview && (
                            <button
                                type="button"
                                className={styles.problemButton}
                                disabled={busy || !availableIssueUnits.length}
                                aria-expanded={issueOpen}
                                onClick={() => {
                                    setIssueUnit(
                                        String(
                                            availableIssueUnits[0]?.id ?? '',
                                        ),
                                    );
                                    setIssueOpen((open) => !open);
                                }}
                            >
                                <PiWarningCircle aria-hidden />
                                Проблема
                            </button>
                        )}
                        {isTechReview && project.qr_ready && (
                            <button
                                className={styles.primary}
                                disabled={busy || !reviewReady}
                                onClick={() => void send({ action: 'release' })}
                            >
                                На комплектовку
                            </button>
                        )}
                    </div>
                    {isTechReview && !project.tech_approved && !reviewReady && (
                        <p className={styles.reviewHint}>
                            Сначала подтвердите техкарты и лекала всех товаров.
                        </p>
                    )}
                    {isTechReview && issueOpen && (
                        <form
                            className={styles.issueForm}
                            onSubmit={(event) => {
                                event.preventDefault();
                                void reportIssue();
                            }}
                        >
                            <label>
                                Товар
                                <select
                                    required
                                    value={issueUnit}
                                    disabled={busy}
                                    onChange={(event) =>
                                        setIssueUnit(event.target.value)
                                    }
                                >
                                    {availableIssueUnits.map((unit) => (
                                        <option key={unit.id} value={unit.id}>
                                            {unit.source.title} ·{' '}
                                            {unit.source.size} · вещь №{unit.id}
                                        </option>
                                    ))}
                                </select>
                            </label>
                            <label>
                                Что нужно проверить
                                <textarea
                                    required
                                    rows={3}
                                    maxLength={1000}
                                    value={issueNote}
                                    disabled={busy}
                                    placeholder="Опишите проблему по товару"
                                    onChange={(event) =>
                                        setIssueNote(event.target.value)
                                    }
                                />
                            </label>
                            <div className={styles.issueActions}>
                                <button
                                    type="button"
                                    disabled={busy}
                                    onClick={() => setIssueOpen(false)}
                                >
                                    Отмена
                                </button>
                                <button
                                    type="submit"
                                    className={styles.problemButton}
                                    disabled={busy || !issueNote.trim()}
                                >
                                    Отправить в проблемы
                                </button>
                            </div>
                        </form>
                    )}
                </div>
            )}
            {!isReview && <h3>Перемещение всего мешка</h3>}
            {!isReview && (
                <div className={styles.actions}>
                    {['kitting', 'waiting_dtf'].includes(project.state) &&
                        canAct(stations, 'kit') && (
                            <button
                                className={styles.primary}
                                disabled={busy || !bagCanMove(project)}
                                onClick={() =>
                                    void send({ action: 'send_bag' })
                                }
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
                                onClick={() =>
                                    void send({ action: 'pack_bag' })
                                }
                            >
                                Все вещи вложены — закрыть упаковку
                            </button>
                        )}
                </div>
            )}
            {project.state === 'waiting_dtf' && (
                <p>
                    Подтвердите вложение плёнки для каждой ожидающей вещи, затем
                    верните весь мешок в цех.
                </p>
            )}
            {project.delivery &&
                (canAct(stations, 'packing') ||
                    canAct(stations, 'shipping')) && (
                    <details open={canAct(stations, 'packing')}>
                        <summary>Получатель и доставка</summary>
                        <p>
                            {project.delivery.recipient} ·{' '}
                            {project.delivery.phone}
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
                            note: shippingNote,
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
                            value={shippingNote}
                            onChange={(event) =>
                                setShippingNote(event.target.value)
                            }
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
