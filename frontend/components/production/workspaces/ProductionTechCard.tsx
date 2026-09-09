'use client';
import { useRef } from 'react';
import { PiArrowLeft } from 'react-icons/pi';
import { labels, type Unit } from '@/lib/production/types';
import { OrderEvidence } from '../OrderEvidence';
import { ProductionViews } from './ProductionViews';
import styles from './ProductionFlow.module.css';

/** Native modal supplies focus containment, Escape and focus restoration. */
export function ProductionTechCard({ unit }: { unit: Unit }) {
    const dialog = useRef<HTMLDialogElement>(null);
    return (
        <>
            <button
                className={styles.cardLink}
                onClick={() => dialog.current?.showModal()}
            >
                Открыть полную карточку вещи →
            </button>
            <dialog
                ref={dialog}
                className={styles.sheet}
                aria-label={`Техкарта: ${unit.source.title}`}
            >
                <header className={styles.sheetHeader}>
                    <button
                        aria-label="Вернуться к мешку"
                        onClick={() => dialog.current?.close()}
                    >
                        <PiArrowLeft />
                    </button>
                    <div>
                        <strong>{unit.source.title}</strong>
                        <small>
                            Вещь #{unit.id} · {unit.source.size}
                        </small>
                    </div>
                </header>
                <div className={styles.sheetBody}>
                    <ProductionViews unit={unit} compact />
                    <OrderEvidence unit={unit} />
                    {unit.specification ? (
                        <>
                            <h2>Техкарта и маршрут</h2>
                            <p>
                                Спецификация #{unit.specification_id} · версия{' '}
                                {unit.revision}
                            </p>
                            <p>{unit.specification.instructions}</p>
                            <ol className={styles.cardRoute}>
                                {unit.specification.route.map(
                                    (stage, index) => (
                                        <li
                                            key={stage}
                                            data-active={
                                                index === unit.stage_index
                                            }
                                        >
                                            <strong>{labels[stage]}</strong>
                                            <small>
                                                {index < unit.stage_index
                                                    ? 'Завершено'
                                                    : index === unit.stage_index
                                                      ? 'Текущий участок'
                                                      : 'Далее'}
                                            </small>
                                        </li>
                                    ),
                                )}
                            </ol>
                            <h2>Комплектующие</h2>
                            {unit.specification.components.map((part) => (
                                <div className={styles.cardPart} key={part.key}>
                                    <strong>{part.name}</strong>
                                    <small>{part.location}</small>
                                    <span>
                                        {part.quantity} {part.unit}
                                    </span>
                                </div>
                            ))}
                            <h2>Проверки ОТК</h2>
                            <ul>
                                {unit.specification.quality_checks.map(
                                    (check) => (
                                        <li key={check}>{check}</li>
                                    ),
                                )}
                            </ul>
                        </>
                    ) : (
                        <p className={styles.callout}>
                            Технолог ещё не закрепил техкарту. Производство
                            недоступно.
                        </p>
                    )}
                </div>
            </dialog>
        </>
    );
}
