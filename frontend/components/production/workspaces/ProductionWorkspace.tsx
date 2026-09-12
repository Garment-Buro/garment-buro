'use client';
import { useState } from 'react';
import Link from 'next/link';
import {
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
import { stationRoles, thingsCount } from '@/lib/production/workspaces';
import { ProductionCycle } from './ProductionCycle';
import { BagScanner } from './BagScanner';
import { ProductionBag } from './ProductionBag';
import { PrintSheet } from '../PrintSheet';
import styles from './ProductionFlow.module.css';
import legacy from '../ProductionTerminal.module.css';

export function ProductionWorkspace() {
    const [chosen, setChosen] = useState<Station | null>(null);
    const terminal = useProductionTerminal(chosen ?? undefined);
    const logout = useProductionAuthStore((s) => s.logout);
    const authError = useProductionAuthStore((s) => s.error);
    const [cycle, setCycle] = useState(false);
    const [pocket, setPocket] = useState('work');
    const [query, setQuery] = useState('');
    const [printing, setPrinting] = useState(false);
    const [printError, setPrintError] = useState('');
    const { employee, project, busy, loading, queue } = terminal;
    const station = chosen ?? employee?.stations[0] ?? 'tech';
    const wide = station === 'tech' || station === 'dtf';
    const print = async () => {
        setPrinting(true);
        setPrintError('');
        try {
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
        }
    };
    const choose = (next: Station) => {
        if (busy) return;
        setChosen(next);
        setCycle(false);
        setPocket('work');
    };
    const relevant = (item: QueueItem) => {
        if (pocket === 'all') return true;
        if (pocket === 'holds')
            return (
                item.state === 'waiting_dtf' ||
                Boolean(item.stage_counts?.waiting_dtf)
            );
        if (pocket === 'done')
            return ['packed', 'dispatched'].includes(item.state);
        if (
            item.flow_version === 2 &&
            station !== 'tech' &&
            station !== 'shipping'
        ) {
            if (station === 'dtf') return (item.dtf_pending ?? 0) > 0;
            if (station === 'kit')
                return Boolean(
                    item.stage_counts?.kit || item.stage_counts?.waiting_dtf,
                );
            return Boolean(item.stage_counts?.[station]);
        }
        if (station === 'tech') return item.state === 'inbox';
        if (station === 'kit') return item.state === 'kitting';
        if (station === 'shipping') return item.state === 'packed';
        if (station === 'dtf')
            return (
                ['kitting', 'workshop', 'waiting_dtf'].includes(item.state) &&
                (item.dtf_pending ?? 0) > 0
            );
        return (
            item.state === 'workshop' && Boolean(item.stage_counts?.[station])
        );
    };
    const items = queue.items
        .filter(relevant)
        .filter((x) =>
            `${x.order_id} ${x.customer}`
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
                </span>
                <PiCaretDown aria-hidden />
            </button>
            {!wide && terminal.selected === item.project_id && detail}
        </article>
    );
    const detail =
        project && employee ? (
            <ProductionBag
                project={project}
                employee={employee}
                station={station}
                busy={busy || loading || printing}
                send={terminal.send}
                print={() => void print()}
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
                    <div className={styles.avatar}>
                        {employee?.name.slice(0, 1) ?? 'GB'}
                    </div>
                    <div className={styles.account}>
                        <small>Аккаунт · Garment Buro</small>
                        <strong title={employee?.name}>
                            {employee?.name ?? 'Сотрудник'}
                        </strong>
                    </div>
                    <span className={styles.role}>{stationRoles[station]}</span>
                    {employee?.can_administer && (
                        <Link
                            className={styles.adminLink}
                            href="/production/admin"
                        >
                            Администратор
                        </Link>
                    )}
                    <button
                        className={styles.logout}
                        aria-label="Выйти из терминала"
                        disabled={busy || printing}
                        onClick={() => void logout()}
                    >
                        <PiSignOut />
                    </button>
                </header>
                <main
                    className={styles.page}
                    data-wide={wide && !cycle}
                    data-cut={station === 'cut' && !cycle}
                >
                    <nav
                        className={styles.modeSwitch}
                        aria-label="Режим терминала"
                    >
                        <button
                            aria-current={!cycle ? 'page' : undefined}
                            onClick={() => setCycle(false)}
                        >
                            Моя работа
                        </button>
                        <button
                            aria-current={cycle ? 'page' : undefined}
                            onClick={() => setCycle(true)}
                        >
                            Весь цикл
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
                                    station === s && !cycle ? 'page' : undefined
                                }
                                disabled={busy || printing}
                                onClick={() => choose(s)}
                            >
                                <b>{i + 1}</b>
                                {labels[s]}
                            </button>
                        ))}
                    </nav>
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
                    <BagScanner
                        disabled={busy || printing}
                        station={station}
                        onOpen={(id, unit) => {
                            setCycle(false);
                            terminal.select(id, unit);
                        }}
                    />
                    {cycle ? (
                        <ProductionCycle
                            assigned={employee?.stations ?? []}
                            onOpen={choose}
                        />
                    ) : (
                        <>
                            <div className={styles.layout}>
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
                                        {[
                                            ['work', 'В работе'],
                                            ['holds', 'Ждут вложения'],
                                            ['done', 'Завершённые'],
                                            ['all', 'Все мешки'],
                                        ].map(([key, label]) => (
                                            <button
                                                key={key}
                                                aria-pressed={pocket === key}
                                                onClick={() => setPocket(key)}
                                            >
                                                {label}
                                            </button>
                                        ))}
                                    </div>
                                    {pocket === 'holds' && (
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
                                            placeholder="Имя или номер заказа"
                                        />
                                    </label>
                                    {loading && !queue.items.length ? (
                                        <div
                                            role="status"
                                            className={styles.skeleton}
                                        >
                                            Загружаем заказы…
                                        </div>
                                    ) : !items.length ? (
                                        <div className={styles.empty}>
                                            <PiPackage />
                                            <h2>Здесь пока нет мешков</h2>
                                            <p>
                                                Проверьте другие состояния или
                                                загрузите следующую часть
                                                списка.
                                            </p>
                                        </div>
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
                                {wide && (
                                    <section className={styles.detail}>
                                        {detail ?? (
                                            <div className={styles.empty}>
                                                <PiPackage />
                                                <h2>Выберите мешок</h2>
                                                <p>
                                                    Здесь появятся вещи,
                                                    развёртки и рабочие
                                                    действия.
                                                </p>
                                            </div>
                                        )}
                                    </section>
                                )}
                            </div>
                            {!wide &&
                                terminal.selected &&
                                !items.some(
                                    (x) => x.project_id === terminal.selected,
                                ) && (
                                    <section className={styles.detail}>
                                        <button
                                            onClick={() =>
                                                terminal.select(null)
                                            }
                                            disabled={busy || printing}
                                        >
                                            Закрыть открытый мешок
                                        </button>
                                        {detail}
                                    </section>
                                )}
                        </>
                    )}
                </main>
            </div>
            {project &&
                employee &&
                (employee.stations.includes('tech') ||
                    employee.stations.includes('dtf') ||
                    employee.stations.includes('cut')) && (
                    <PrintSheet
                        project={project}
                        unitSheets={
                            project.flow_version === 2
                                ? station === 'cut'
                                : station === 'tech'
                        }
                    />
                )}
        </>
    );
}
