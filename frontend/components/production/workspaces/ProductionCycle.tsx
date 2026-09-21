import { labels, type Station } from '@/lib/production/types';
import { stationGuides, stationRoles } from '@/lib/production/workspaces';
import styles from './ProductionFlow.module.css';

export function ProductionCycle({
    station,
    onOpen,
}: {
    station: Station;
    onOpen: (station: Station) => void;
}) {
    const guide = stationGuides[station];
    return (
        <section className={styles.cycle}>
            <h1>Моя работа · {stationRoles[station]}</h1>
            <p>
                Краткая методичка для выбранной роли. Здесь нет заказов и
                рабочих кнопок — только порядок действий и ожидаемый результат.
            </p>
            <article className={styles.roleGuide}>
                <span className={styles.roleGuideLabel}>{labels[station]}</span>
                <h2>Что сделать</h2>
                <p>{guide.task}</p>
                <h2>Результат</h2>
                <p>{guide.result}</p>
                <button onClick={() => onOpen(station)}>
                    Открыть терминал роли →
                </button>
            </article>
        </section>
    );
}
