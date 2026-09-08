import type { Project } from '@/lib/production/types';
import { labels } from '@/lib/production/types';
import styles from './ProductionTerminal.module.css';
export function PrintSheet({
    project,
    unitSheets,
}: {
    project: Project;
    unitSheets: boolean;
}) {
    const qr = (unit?: number) =>
        `/api/qr-code?surface=production&size=512&path=${encodeURIComponent(`/production?project=${project.project_id}${unit ? `&unit=${unit}#unit-${unit}` : ''}`)}`;
    return (
        <div className={styles.printSheets} aria-hidden="true">
            <section>
                <h1>GARMENT BURO · МЕШОК</h1>
                <h2>Заказ №{project.order_id}</h2>
                <p>
                    {project.units_count} вещей · проект #{project.project_id}
                </p>
                {/* eslint-disable-next-line @next/next/no-img-element -- generated QR */}
                <img
                    data-production-qr
                    src={qr()}
                    width={180}
                    height={180}
                    alt="QR мешка"
                />
                <p>
                    Один заказ — один мешок. Проверяйте актуальное состояние в
                    терминале.
                </p>
                <ul>
                    {project.units.map((unit) => (
                        <li key={unit.id}>
                            #{unit.id} · {unit.source.title} ·{' '}
                            {unit.source.size} · {unit.source.color}
                        </li>
                    ))}
                </ul>
            </section>
            {unitSheets &&
                project.units.map((unit) => (
                    <section key={unit.id}>
                        <h1>
                            ВЕЩЬ #{unit.id} · ЗАКАЗ №{project.order_id}
                        </h1>
                        <h2>
                            {unit.source.title} · {unit.source.size} ·{' '}
                            {unit.source.color}
                        </h2>
                        {/* eslint-disable-next-line @next/next/no-img-element -- generated QR */}
                        <img
                            data-production-qr
                            src={qr(unit.id)}
                            width={150}
                            height={150}
                            alt={`QR вещи ${unit.id}`}
                        />
                        <p>
                            Спецификация #{unit.specification_id ?? '—'} ·
                            версия {unit.revision ?? 'не подготовлена'}
                        </p>
                        {unit.specification ? (
                            <>
                                <p>
                                    {unit.specification.route
                                        .map((x) => labels[x])
                                        .join(' → ')}
                                </p>
                                <p>{unit.specification.instructions}</p>
                                <ul>
                                    {unit.specification.components.map((x) => (
                                        <li key={x.key}>
                                            □ {x.name} · {x.quantity} {x.unit} ·{' '}
                                            {x.location}
                                        </li>
                                    ))}
                                </ul>
                                <h3>ОТК</h3>
                                <ul>
                                    {unit.specification.quality_checks.map(
                                        (x) => (
                                            <li key={x}>□ {x}</li>
                                        ),
                                    )}
                                </ul>
                                <p>
                                    Лекала:{' '}
                                    {unit.specification.pattern_file_ids.join(
                                        ', ',
                                    ) || 'не требуются'}{' '}
                                    · DTF:{' '}
                                    {unit.specification.print_file_ids.join(
                                        ', ',
                                    ) || 'не требуется'}
                                </p>
                            </>
                        ) : (
                            <p>НЕ ВЫПУСКАТЬ В РАБОТУ — нет спецификации</p>
                        )}
                    </section>
                ))}
        </div>
    );
}
