import { labels, stations, type Station } from '@/lib/production/types';
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
            <p>Один заказ — один мешок. У каждой вещи свой маршрут.</p>
            <aside className={styles.callout}>
                DTF печатается параллельно. Ожидание плёнки и её вложение не
                заменяют участок нанесения.
            </aside>
            {stations.map((station, index) => (
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
                        <button onClick={() => onOpen(station)}>
                            Открыть рабочий экран →
                        </button>
                    </div>
                </details>
            ))}
        </section>
    );
}
