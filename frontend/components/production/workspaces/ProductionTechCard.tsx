'use client';
import { useRef } from 'react';
import { PiArrowLeft } from 'react-icons/pi';
import { labels, type Unit } from '@/lib/production/types';
import { visibleInstructions } from '@/lib/production/workflow';
import { OrderEvidence } from '../OrderEvidence';
import { ProductionViews } from './ProductionViews';
import styles from './ProductionFlow.module.css';

const operationLabels: Record<string, string> = { ...labels, sewing: 'Пошив', press: 'ВТО', qc: 'Контроль качества' };

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
                    <TechCardContent unit={unit} />
                </div>
            </dialog>
        </>
    );
}

export function TechCardContent({ unit }: { unit: Unit }) {
    const card = unit.tech_card ?? unit.cards.find(
        (item) => item.id === unit.specification?.tech_card_revision_id,
    );
    return (
        <>
            <section className={styles.modelTechCard}>
                <h2>Техкарта модели</h2>
                {card ? (
                    <>
                        <h3>{card.name} · версия {card.revision}</h3>
                        <p>Закреплённая версия для этой вещи. Техкарта ведётся в модели.</p>
                        {card.description && <p className={styles.cardText}>{card.description}</p>}
                        <ol className={styles.checkpointList}>
                            {card.checkpoints?.map((point) => (
                                <li key={point.position}>
                                    <strong>{point.name}</strong>
                                    <small>
                                        {operationLabels[point.stage_code] ?? point.stage_code}
                                        {point.standard_minutes ? ` · ${Number(point.standard_minutes)} мин` : ''}
                                    </small>
                                    {point.description && <p className={styles.cardText}>{point.description}</p>}
                                </li>
                            ))}
                        </ol>
                        {!card.checkpoints?.length && <p>Операции техкарты не указаны.</p>}
                    </>
                ) : <p>Техкарта модели ещё не закреплена в задании на вещь.</p>}
            </section>
            {unit.specification ? (
                <>
                    <h2>Задание на эту вещь</h2>
                    <p>
                        Спецификация #{unit.specification_id} · версия{' '}
                        {unit.revision}
                    </p>
                    {visibleInstructions(unit.specification.instructions) && (
                        <p className={styles.cardText}>{visibleInstructions(unit.specification.instructions)}</p>
                    )}
                    <ol className={styles.cardRoute}>
                        {unit.specification.route.map(
                            (stage, index) => (
                                <li
                                    key={stage}
                                    data-active={
                                        index === unit.stage_index
                                    }
                                >
                                    <strong>{operationLabels[stage]}</strong>
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
                    <h2>Проверки качества</h2>
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
                    Технолог ещё не закрепил задание на вещь. Производство
                    недоступно.
                </p>
            )}

        </>
    );
}
