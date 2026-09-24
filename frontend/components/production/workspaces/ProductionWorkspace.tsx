'use client';
import { useState } from 'react';
import Link from 'next/link';
import {
    PiArrowLeft,
    PiArrowClockwise,
    PiCaretDown,
    PiPackage,
    PiSignOut,
} from 'react-icons/pi';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import { useProductionTerminal } from '@/hooks/production/useProductionTerminal';
import {
    labels,
    stateLabels,
    type QueueItem,
    type Station,
} from '@/lib/production/types';
import {
    queueItemMatchesPocket,
    queueItemMatchesStation,
    stationRoles,
    thingsCount,
    type QueuePocket,
} from '@/lib/production/workspaces';
import { ProductionCycle } from './ProductionCycle';
import { BagScanner } from './BagScanner';
import { ProductionBag } from './ProductionBag';
import { PrintSheet, type PrintTarget } from '../PrintSheet';
import { ProductionMark, TerminalState } from './ProductionUi';
import styles from './ProductionFlow.module.css';
import legacy from '../ProductionTerminal.module.css';

export function ProductionWorkspace() {
    const [chosen, setChosen] = useState<Station | null>(null);
    const terminal = useProductionTerminal(chosen ?? undefined);
    const logout = useProductionAuthStore((s) => s.logout);
    const authError = useProductionAuthStore((s) => s.error);
    const [cycle, setCycle] = useState(false);
    const [pocket, setPocket] = useState<QueuePocket>('work');
    const [query, setQuery] = useState('');
    const [printing, setPrinting] = useState(false);
    const [printTarget, setPrintTarget] = useState<PrintTarget | null>(null);
    const [printError, setPrintError] = useState('');
    const { employee, project, busy, loading, queue } = terminal;
    const station = chosen ?? employee?.stations[0] ?? 'tech';
    const print = async (target: PrintTarget) => {
        setPrinting(true);
        setPrintTarget(target);
        setPrintError('');
        try {
            await new Promise<void>((resolve) =>
                requestAnimationFrame(() => resolve()),
            );
            const images = Array.from(
                document.querySelectorAll<HTMLImageElement>(
                    '[data-production-qr]',
                ),
            );
            if (!images.length) throw new Error();
            await Promise.all(images.map((image) => image.decode()));
            window.print();
        } catch {
            setPrintError(
                'QR не загрузились. Проверьте соединение и повторите печать.',
            );
        } finally {
            setPrinting(false);
            setPrintTarget(null);
        }
    };
    const choose = (next: Station) => {
        if (busy) return;
        setChosen(next);
        setCycle(false);
        setPocket('work');
    };
    if (employee && employee.stations.length === 0) {
        return (
            <main className={legacy.login}>
                <section className={legacy.panel}>
                    <p className={legacy.eyebrow}>GARMENT BURO · ПРОИЗВОДСТВО</p>
                    <h1>Нет назначенного участка</h1>
                    <p>
                        Администраторская роль открывает управление, но не даёт
                        права выполнять операции цеха. Назначьте себе участок в
                        разделе сотрудников, если нужен доступ к рабочему
                        терминалу.
                    </p>
                    {employee.can_administer && (
                        <Link href="/production">Вернуться в админку</Link>
                    )}
                </section>
            </main>
        );
    }
    const relevant = (item: QueueItem) => {
        if (pocket !== 'work')
            return (
                queueItemMatchesStation(item, station) &&
                queueItemMatchesPocket(item, pocket)
            );
        return queueItemMatchesStation(item, station);
    };
    const items = queue.items
        .filter(relevant)
        .filter((x) =>
            `${x.order_id} ${x.project_id} ${x.customer}`
                .toLowerCase()
                .includes(query.toLowerCase()),
        );
    const renderBag = (item: QueueItem) => (
        <article
            className={styles.bag}
            data-tone={item.state === 'waiting_dtf' ? 'wait' : 'work'}
            key={item.project_id}
        >
            <button
                className={styles.bagToggle}
                aria-expanded={terminal.selected === item.project_id}
                disabled={busy || printing}
                onClick={() =>
                    terminal.select(
                        terminal.selected === item.project_id
                            ? null
                            : item.project_id,
                    )
                }
            >
                <span className={styles.bagIcon}>
                    <PiPackage aria-hidden />
                </span>
                <span>
                    <strong>{item.customer}</strong>
                    <small>
                        {item.is_demo && 'ТЕСТ · '}
                        Заказ №{item.order_id} · {thingsCount(item.units_count)}
                    </small>
                    <em>
                        {item.blocked
                            ? 'Работа остановлена'
                            : stateLabels[item.display_state || item.state]}
                    </em>
                    {station === 'dtf' && Boolean(item.dtf_overdue) && (
                        <em className={styles.overdue}>
                            Просрочено: {item.dtf_overdue}
                        </em>
                    )}
                </span>
                <PiCaretDown aria-hidden />
            </button>
        </article>
    );
    const detail =
        project && employee ? (
            <ProductionBag
                key={`${project.project_id}-${station}-${terminal.focusedUnit ?? 'root'}`}
                project={project}
                employee={employee}
                station={station}
                busy={busy || loading || printing}
                send={terminal.send}
                print={(target) => void print(target)}
                printing={printing}
                requestedUnit={terminal.focusedUnit}
            />
        ) : terminal.selected && loading ? (
            <div className={styles.skeleton} role="status">
                Загружаем состав мешка…
            </div>
        ) : null;
    return (
        <>
            <div className={`${legacy.terminal} ${styles.flow}`}>
                <header className={styles.topbar}>
                    <div className={styles.topbarInner}>
                        <ProductionMark />
                        <div className={styles.account}>
                            <small>Производственный терминал</small>
                            <strong title={employee?.name}>
                                {employee?.name ?? 'Сотрудник'}
                            </strong>
                        </div>
                        <span className={styles.role}>
                            {stationRoles[station]}
                        </span>
                        {employee?.can_administer && (
                            <Link
                                className={styles.adminLink}
                                href="/production"
                            >
                                Администратор
                            </Link>
                        )}
                        <button
                            className={styles.logout}
                            aria-label="Выйти из терминала"
                            title="Выйти"
                            disabled={busy || printing}
                            onClick={() => void logout()}
                        >
                            <PiSignOut aria-hidden="true" />
                        </button>
                    </div>
                </header>
                <main className={styles.page}>
                    <div className={styles.navigation}>
                        <nav
                            className={styles.modeSwitch}
                            aria-label="Режим терминала"
                        >
                            <button
                                aria-current={!cycle ? 'page' : undefined}
                                onClick={() => setCycle(false)}
                            >
                                Терминал
                            </button>
                            <button
                                aria-current={cycle ? 'page' : undefined}
                                onClick={() => setCycle(true)}
                            >
                                Моя работа
                            </button>
                        </nav>
                        <nav
                            className={styles.processNav}
                            aria-label="Производственный контур"
                        >
                            {(employee?.stations ?? []).map((s, i) => (
                                <button
                                    key={s}
                                    aria-current={
                                        station === s && !cycle
                                            ? 'page'
                                            : undefined
                                    }
                                    disabled={busy || printing}
                                    onClick={() => choose(s)}
                                >
                                    <b>{i + 1}</b>
                                    {stationRoles[s]}
                                </button>
                            ))}
                        </nav>
                    </div>
                    <div aria-live="polite">
                        {employee?.is_demo && (
                            <p className={styles.notice}>
                                Учебный режим. Только тестовые заказы, без
                                оплаты и реальной отправки. Файлы примеров не
                                являются производственными лекалами.
                            </p>
                        )}
                        {(terminal.error || printError || authError) && (
                            <p className={styles.error} role="alert">
                                {terminal.error || printError || authError}
                            </p>
                        )}
                        {terminal.notice && (
                            <p className={styles.notice}>{terminal.notice}</p>
                        )}
                    </div>
                    {!cycle && (
                        <BagScanner
                            disabled={busy || printing}
                            station={station}
                            onOpen={(id, unit) => {
                                setCycle(false);
                                terminal.select(id, unit);
                            }}
                        />
                    )}
                    {cycle ? (
                        <ProductionCycle station={station} />
                    ) : (
                        <>
                            <div
                                className={styles.layout}
                                data-selected={Boolean(terminal.selected)}
                            >
                                <section className={styles.queue}>
                                    <div className={styles.queueHeading}>
                                        <div>
                                            <h1>
                                                {station === 'kit'
                                                    ? 'Мешки комплектовщика'
                                                    : station === 'dtf'
                                                      ? 'Заказы на DTF'
                                                      : labels[station]}
                                            </h1>
                                            <p>
                                                {station === 'tech'
                                                    ? 'Проверить заказ, выпустить QR и лекала.'
                                                    : station === 'dtf'
                                                      ? 'Файлы, печать, QR мешка и готовность к забору.'
                                                      : 'Каждая вещь остаётся в своём мешке.'}
                                            </p>
                                        </div>
                                        <button
                                            aria-label="Обновить заказы"
                                            disabled={
                                                busy || loading || printing
                                            }
                                            onClick={terminal.reload}
                                        >
                                            <PiArrowClockwise />
                                        </button>
                                    </div>
                                    <div
                                        className={styles.pockets}
                                        role="group"
                                        aria-label="Состояние мешков"
                                    >
                                        {(station === 'kit'
                                            ? ([
                                                  ['purchase', 'Закупка'],
                                                  ['work', 'В работе'],
                                                  ['waiting_dtf', 'Ожидание DTF'],
                                              ] as [QueuePocket, string][])
                                            : ([
                                                  ['work', 'В работе'],
                                                  ['holds', 'Ждут вложения'],
                                                  ['done', 'Завершённые'],
                                                  ['all', 'Все мешки'],
                                              ] as [QueuePocket, string][])
                                        ).map(([key, label]) => (
                                            <button
                                                key={key}
                                                aria-pressed={pocket === key}
                                                onClick={() => setPocket(key)}
                                            >
                                                {label}
                                            </button>
                                        ))}
                                    </div>
                                    {(pocket === 'holds' ||
                                        pocket === 'waiting_dtf') && (
                                        <p className={styles.callout}>
                                            Ожидание DTF — статус мешка, не этап
                                            работы.
                                        </p>
                                    )}
                                    <label className={styles.search}>
                                        Поиск по загруженным мешкам
                                        <input
                                            value={query}
                                            onChange={(e) =>
                                                setQuery(e.target.value)
                                            }
                                            placeholder="Имя, заказ или проект"
                                        />
                                    </label>
                                    {loading && !queue.items.length ? (
                                        <TerminalState loading>
                                            Загружаем заказы…
                                        </TerminalState>
                                    ) : !items.length ? (
                                        <TerminalState title="Здесь пока нет мешков">
                                            Проверьте другие состояния или
                                            загрузите следующую часть списка.
                                        </TerminalState>
                                    ) : (
                                        items.map(renderBag)
                                    )}
                                    {queue.next_cursor && (
                                        <button
                                            disabled={busy || printing}
                                            onClick={() => void terminal.more()}
                                        >
                                            Загрузить ещё
                                        </button>
                                    )}
                                </section>
                                <section className={styles.detail}>
                                    {terminal.selected && (
                                        <button
                                            className={styles.mobileDetailBack}
                                            onClick={() => terminal.select(null)}
                                            disabled={busy || printing}
                                        >
                                            <PiArrowLeft aria-hidden="true" />
                                            К списку мешков
                                        </button>
                                    )}
                                    {detail ?? (
                                        <TerminalState
                                            title={
                                                terminal.selected && loading
                                                    ? undefined
                                                    : 'Выберите мешок'
                                            }
                                            loading={
                                                Boolean(terminal.selected) &&
                                                loading
                                            }
                                        >
                                            {terminal.selected && loading
                                                ? 'Загружаем состав мешка…'
                                                : 'Здесь появятся вещи, развёртки и рабочие действия.'}
                                        </TerminalState>
                                    )}
                                </section>
                            </div>
                        </>
                    )}
                </main>
            </div>
            {project && employee && printTarget !== null && (
                    <PrintSheet
                        project={project}
                        onlyReadyDtf={station === 'dtf'}
                        target={printTarget}
                    />
                )}
        </>
    );
}
