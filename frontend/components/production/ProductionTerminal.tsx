'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ProductionAdminTerminal } from './admin/ProductionAdminTerminal';
import {
    PiArrowClockwise,
    PiPackage,
    PiPrinter,
    PiSignOut,
    PiMagnifyingGlass,
} from 'react-icons/pi';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import { useProductionTerminal } from '@/hooks/production/useProductionTerminal';
import {
    actionLabels,
    labels,
    stateLabels,
    stations,
    type Station,
} from '@/lib/production/types';
import { matchesStation, orderBlocked } from '@/lib/production/workflow';
import { ProductionLogin } from './ProductionLogin';
import { ProductionUnit } from './ProductionUnit';
import { BagActions } from './BagActions';
import { PrintSheet } from './PrintSheet';
import styles from './ProductionTerminal.module.css';

function Workspace() {
    const terminal = useProductionTerminal();
    const logout = useProductionAuthStore((state) => state.logout);
    const authError = useProductionAuthStore((state) => state.error);
    const [station, setStation] = useState<Station | 'cycle'>('tech');
    const [search, setSearch] = useState('');
    const [printError, setPrintError] = useState('');
    const [printing, setPrinting] = useState(false);
    const print = async () => {
        setPrinting(true);
        setPrintError('');
        try {
            const images = Array.from(
                document.querySelectorAll<HTMLImageElement>(
                    '[data-production-qr]',
                ),
            );
            if (!images.length) throw new Error('QR ещё не подготовлены');
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
    const { employee, project, busy, loading } = terminal;
    const blocked = project ? orderBlocked(project) : false;
    const items = terminal.queue.items.filter((x) =>
        `${x.order_id} ${x.project_id} ${x.customer}`
            .toLowerCase()
            .includes(search.toLowerCase()),
    );
    return (
        <>
            <main className={styles.terminal}>
                <header className={styles.header}>
                    <div className={styles.brand}>GB</div>
                    <div className={styles.grow}>
                        <p className={styles.eyebrow}>GARMENT BURO</p>
                        <h1>Производство</h1>
                    </div>
                    <span className={styles.employee}>
                        {employee?.name ?? 'Терминал'}
                    </span>
                    {employee?.can_administer && <Link href="/production/admin">Администратор</Link>}
                    <button disabled={busy} onClick={() => void logout()}>
                        <PiSignOut aria-hidden />
                        Выйти
                    </button>
                </header>
                <nav className={styles.tabs} aria-label="Участки производства">
                    {stations.map((x) => (
                        <button
                            key={x}
                            aria-current={station === x ? 'page' : undefined}
                            onClick={() => setStation(x)}
                        >
                            {labels[x]}
                            {employee?.stations.includes(x) && (
                                <span
                                    className={styles.dot}
                                    aria-label="Ваш участок"
                                />
                            )}
                        </button>
                    ))}
                    <button
                        aria-current={station === 'cycle' ? 'page' : undefined}
                        onClick={() => setStation('cycle')}
                    >
                        Весь цикл
                    </button>
                </nav>
                <div className={styles.messages} aria-live="polite">
                    {authError && <p role="alert" className={styles.error}>{authError}</p>}
                    {printError && (
                        <p className={styles.error} role="alert">
                            {printError}
                        </p>
                    )}
                    {terminal.error && (
                        <p className={styles.error} role="alert">
                            {terminal.error}
                        </p>
                    )}
                    {terminal.notice && (
                        <p className={styles.success}>{terminal.notice}</p>
                    )}
                </div>
                {station === 'cycle' && (
                    <section className={styles.cycle}>
                        <h2>Один заказ — один мешок</h2>
                        <p>
                            Входящие → Комплектовка → Раскрой → Нанесение →
                            Пошив → ВТО → ОТК → Упаковка → Отправка
                        </p>
                        <p>
                            DTF печатается параллельно. Готовность печати и её
                            вложение в мешок подтверждают разные участки. При
                            ожидании DTF доступные вещи проходят свой маршрут;
                            весь мешок возвращается на стол ожидания.
                        </p>
                    </section>
                )}
                <div className={styles.workspace}>
                    <aside className={styles.queue}>
                        <div className={styles.row}>
                            <h2 className={styles.grow}>Заказы</h2>
                            <button
                                aria-label="Обновить заказы"
                                disabled={busy || loading}
                                onClick={terminal.reload}
                            >
                                <PiArrowClockwise aria-hidden />
                            </button>
                        </div>
                        <label className={styles.search}>
                            <PiMagnifyingGlass aria-hidden />
                            <input
                                aria-label="Поиск среди загруженных заказов"
                                placeholder="Номер или имя"
                                value={search}
                                onChange={(event) =>
                                    setSearch(event.target.value)
                                }
                            />
                        </label>
                        <p className={styles.muted}>
                            Оплаченные заказы · {terminal.queue.items.length}{' '}
                            загружено
                        </p>
                        {loading && !items.length ? (
                            <p role="status">Загружаем заказы…</p>
                        ) : (
                            items.length === 0 && (
                                <div className={styles.empty}>
                                    <PiPackage aria-hidden />
                                    <h3>
                                        {employee
                                            ? 'Заказов пока нет'
                                            : 'Нет доступа к заказам'}
                                    </h3>
                                    <p>
                                        {employee
                                            ? 'Здесь появятся оплаченные заказы после передачи в производство. Поиск работает по загруженной части списка.'
                                            : 'Войдите с производственной ролью. Если терминал выключен, его должен включить администратор.'}
                                    </p>
                                </div>
                            )
                        )}
                        {items.map((item) => (
                            <button
                                className={styles.queueItem}
                                aria-pressed={
                                    terminal.selected === item.project_id
                                }
                                disabled={busy}
                                key={item.project_id}
                                onClick={() => terminal.select(item.project_id)}
                            >
                                <span className={styles.row}>
                                    <strong>Заказ №{item.order_id}</strong>
                                    <span
                                        className={
                                            item.blocked
                                                ? styles.dangerBadge
                                                : styles.badge
                                        }
                                    >
                                        {item.blocked
                                            ? 'Остановлен'
                                            : stateLabels[item.state]}
                                    </span>
                                </span>
                                <span>{item.customer}</span>
                                <small>
                                    {item.units_count} вещей ·{' '}
                                    {new Date(item.paid_at).toLocaleDateString(
                                        'ru-RU',
                                    )}
                                </small>
                            </button>
                        ))}
                        {terminal.queue.next_cursor && (
                            <button
                                disabled={busy}
                                onClick={() => void terminal.more()}
                            >
                                Загрузить ещё
                            </button>
                        )}
                    </aside>
                    <section
                        className={styles.detail}
                        aria-busy={loading || busy}
                    >
                        {loading && terminal.selected ? (
                            <p role="status">Загружаем состав мешка…</p>
                        ) : project && employee ? (
                            <>
                                <div className={styles.detailHeader}>
                                    <div>
                                        <p className={styles.eyebrow}>
                                            МЕШОК · {stateLabels[project.state]}
                                        </p>
                                        <h2>Заказ №{project.order_id}</h2>
                                        <p>
                                            {project.customer} ·{' '}
                                            {project.units_count} вещей · версия{' '}
                                            {project.version}
                                        </p>
                                    </div>
                                    {(employee.stations.includes('tech') ||
                                        employee.stations.includes('dtf')) && (
                                        <button
                                            disabled={
                                                busy ||
                                                printing ||
                                                !project.units.every(
                                                    (x) => x.specification,
                                                )
                                            }
                                            onClick={() => void print()}
                                        >
                                            <PiPrinter aria-hidden />
                                            {employee.stations.includes('tech')
                                                ? 'QR и листы вещей'
                                                : 'QR мешка для DTF'}
                                        </button>
                                    )}
                                </div>
                                <p className={styles.muted}>
                                    Просматривать можно весь цикл. Действия
                                    доступны вашим участкам; изменения
                                    сохраняются на сервере.
                                </p>
                                {blocked && (
                                    <p role="alert" className={styles.warning}>
                                        Заказ недоступен для работы: оплата{' '}
                                        {project.payment_status}, заказ{' '}
                                        {project.order_status}, производство{' '}
                                        {project.project_status}.
                                    </p>
                                )}
                                <BagActions
                                    key={`bag-${project.project_id}`}
                                    project={project}
                                    stations={employee.stations}
                                    send={terminal.send}
                                    busy={busy || blocked}
                                />
                                {project.units.map((unit) => (
                                    <div
                                        key={unit.id}
                                        className={
                                            station !== 'cycle' &&
                                            !matchesStation(unit, station)
                                                ? styles.secondaryUnit
                                                : undefined
                                        }
                                    >
                                        <ProductionUnit
                                            key={`${unit.id}-${project.version}`}
                                            unit={unit}
                                            project={project}
                                            stations={employee.stations}
                                            station={
                                                station === 'cycle'
                                                    ? 'tech'
                                                    : station
                                            }
                                            send={terminal.send}
                                            busy={busy || blocked}
                                        />
                                    </div>
                                ))}
                                <details className={styles.section}>
                                    <summary>
                                        Журнал · последние{' '}
                                        {project.events.length} действий
                                    </summary>
                                    <ol className={styles.history}>
                                        {project.events.map((event) => (
                                            <li key={event.id}>
                                                <span>
                                                    {actionLabels[
                                                        event.action
                                                    ] ?? event.action}
                                                    {event.unit_id
                                                        ? ` · вещь #${event.unit_id}`
                                                        : ''}
                                                </span>
                                                <small>
                                                    {new Date(
                                                        event.at,
                                                    ).toLocaleString(
                                                        'ru-RU',
                                                    )}{' '}
                                                    · сотрудник #
                                                    {event.actor_id} · v
                                                    {event.version}
                                                </small>
                                                {event.note && (
                                                    <p>{event.note}</p>
                                                )}
                                            </li>
                                        ))}
                                    </ol>
                                </details>
                            </>
                        ) : (
                            <div className={styles.empty}>
                                <PiPackage aria-hidden />
                                <h2>Выберите мешок заказа</h2>
                                <p>
                                    Состав, файлы, маршрут каждой вещи и история
                                    работы — в одной карточке. QR открывает
                                    нужный заказ после входа.
                                </p>
                            </div>
                        )}
                    </section>
                </div>
            </main>
            {project &&
                employee &&
                (employee.stations.includes('tech') ||
                    employee.stations.includes('dtf')) && (
                    <PrintSheet
                        project={project}
                        unitSheets={employee.stations.includes('tech')}
                    />
                )}
        </>
    );
}
export function ProductionTerminal({ mode = 'auto' }: { mode?: 'auto' | 'admin' | 'floor' }) {
    const initialize = useProductionAuthStore((state) => state.initialize);
    useEffect(() => { void initialize(); }, [initialize]);
    const ready = useProductionAuthStore((state) => state.isSessionReady);
    const authenticated = useProductionAuthStore((state) => state.isAuthenticated);
    const userId = useProductionAuthStore((state) => state.user?.id);
    const canAdminister = useProductionAuthStore((state) => state.user?.can_administer);
    if (!ready)
        return (
            <main className={styles.login}>
                <p role="status">Проверяем рабочую сессию…</p>
            </main>
        );
    if (!authenticated) return <ProductionLogin admin={mode === 'admin'} />;
    if (canAdminister && mode !== 'floor') return <ProductionAdminTerminal key={userId} />;
    if (mode === 'admin') return <main className={styles.login}><h1>Нет доступа</h1><p>Войдите личным кодом администратора.</p><Link href="/production">Вернуться в терминал</Link></main>;
    return <Workspace key={userId} />;
}
