import type { IconType } from 'react-icons';
import {
    PiArrowRight,
    PiCheckCircle,
    PiClipboardText,
    PiNeedle,
    PiPackage,
    PiPrinter,
    PiScissors,
    PiTruck,
    PiWaves,
} from 'react-icons/pi';
import type { Station } from '@/lib/production/types';
import { stationGuides, stationRoles } from '@/lib/production/workspaces';
import styles from './ProductionFlow.module.css';

const cycleSteps: {
    title: string;
    role: string;
    description: string;
    stations: Station[];
    icon: IconType;
}[] = [
    {
        title: 'Проверка заказа',
        role: 'Технолог + DTF',
        description: 'Сверяют макет, техкарту, лекала и подтверждают запуск.',
        stations: ['tech'],
        icon: PiClipboardText,
    },
    {
        title: 'Раскрой',
        role: 'Закройщик',
        description: 'Готовит крой по оригинальным лекалам и размерам заказа.',
        stations: ['cut'],
        icon: PiScissors,
    },
    {
        title: 'DTF',
        role: 'DTF-печатник',
        description: 'Печатает и нарезает нанесения для конкретной вещи.',
        stations: ['dtf'],
        icon: PiPrinter,
    },
    {
        title: 'Комплектовка',
        role: 'Комплектовщик',
        description: 'Собирает ткань, крой, DTF и фурнитуру в один мешок.',
        stations: ['kit'],
        icon: PiPackage,
    },
    {
        title: 'Цех',
        role: 'Мастера цеха',
        description: 'Выполняют нанесение и пошив по закреплённой техкарте.',
        stations: ['workshop', 'application', 'sewing', 'qc'],
        icon: PiNeedle,
    },
    {
        title: 'ВТО',
        role: 'ВТО',
        description: 'Приводит изделие в готовый вид и проверяет результат.',
        stations: ['press'],
        icon: PiWaves,
    },
    {
        title: 'Упаковка',
        role: 'Упаковщик',
        description: 'Сверяет состав мешка и упаковывает готовые вещи.',
        stations: ['packing'],
        icon: PiCheckCircle,
    },
    {
        title: 'Отправка',
        role: 'Отправка',
        description: 'Проверяет получателя и передаёт заказ перевозчику.',
        stations: ['shipping'],
        icon: PiTruck,
    },
];

export function ProductionCycle({ station }: { station: Station }) {
    const guide = stationGuides[station];
    return (
        <section className={styles.cycle}>
            <header className={styles.cycleHeading}>
                <div>
                    <span className={styles.roleGuideLabel}>Моя работа</span>
                    <h1>{stationRoles[station]}</h1>
                    <p>
                        Ваша задача и место в общем производственном процессе.
                    </p>
                </div>
            </header>
            <article className={styles.roleGuide}>
                <div>
                    <small>Что сделать</small>
                    <strong>{guide.task}</strong>
                </div>
                <PiArrowRight aria-hidden />
                <div>
                    <small>Что должно получиться</small>
                    <strong>{guide.result}</strong>
                </div>
            </article>
            <div className={styles.cycleSectionHeading}>
                <div>
                    <h2>Весь цикл заказа</h2>
                    <p>Подсвечен участок, на котором вы сейчас работаете.</p>
                </div>
            </div>
            <ol className={styles.cycleGrid}>
                {cycleSteps.map((step, index) => {
                    const Icon = step.icon;
                    const current = step.stations.includes(station);
                    return (
                        <li key={step.title} data-current={current}>
                            <div className={styles.cycleCardTop}>
                                <span className={styles.cycleIllustration}>
                                    <Icon aria-hidden />
                                </span>
                                <b>{String(index + 1).padStart(2, '0')}</b>
                            </div>
                            <strong>{step.title}</strong>
                            <small>{step.role}</small>
                            <p>{step.description}</p>
                            {current && <em>Вы здесь</em>}
                        </li>
                    );
                })}
            </ol>
        </section>
    );
}
