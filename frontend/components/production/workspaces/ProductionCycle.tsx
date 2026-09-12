import { labels, type Station } from '@/lib/production/types';
import { stationGuides, stationRoles } from '@/lib/production/workspaces';
import styles from './ProductionFlow.module.css';

export function ProductionCycle({
    assigned,
    onOpen,
}: {
    assigned: Station[];
    onOpen: (station: Station) => void;
}) {
    return (
        <section className={styles.cycle}>
            <h1>Весь цикл</h1>
            <p>
                Холд ЮKassa → модерация → подтверждение списания → технолог.
                Один мешок заказа содержит отдельные мешки изделий.
            </p>
            <aside className={styles.callout}>
                После раскроя вещи без DTF сразу комплектуются. Остальные
                ожидают доставку наклейки. Готовые мешки изделий передаются в
                общий цех независимо друг от друга.
            </aside>
            {(
                [
                    'tech',
                    'cut',
                    'dtf',
                    'kit',
                    'workshop',
                    'packing',
                    'shipping',
                ] as Station[]
            ).map((station, index) => (
                <details
                    className={styles.cycleStep}
                    key={station}
                    open={assigned.includes(station)}
                >
                    <summary>
                        <b>{index + 1}</b>
                        <span>
                            <strong>{labels[station]}</strong>
                            <small>
                                {stationRoles[station]}
                                {assigned.includes(station)
                                    ? ' · ваш участок'
                                    : ''}
                            </small>
                        </span>
                    </summary>
                    <div>
                        <h3>Что сделать</h3>
                        <p>{stationGuides[station].task}</p>
                        <h3>Результат</h3>
                        <p>{stationGuides[station].result}</p>
                        <button
                            disabled={!assigned.includes(station)}
                            onClick={() => onOpen(station)}
                        >
                            Открыть рабочий экран →
                        </button>
                    </div>
                </details>
            ))}
        </section>
    );
}
