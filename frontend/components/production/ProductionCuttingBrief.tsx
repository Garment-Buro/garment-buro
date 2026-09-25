import { PiMapPinLine, PiRuler, PiScissors } from 'react-icons/pi';
import type { Unit } from '@/lib/production/types';
import styles from './ProductionTerminal.module.css';

function centimeters(value: number | null) {
    return value == null ? '—' : `${value.toLocaleString('ru-RU')} см`;
}

export function ProductionCuttingBrief({ unit }: { unit: Unit }) {
    const cutting = unit.cutting;
    const fabric = cutting?.fabric;
    return (
        <section className={styles.cuttingBrief} aria-labelledby={`cut-${unit.id}`}>
            <header>
                <span>
                    <PiScissors aria-hidden />
                </span>
                <div>
                    <h4 id={`cut-${unit.id}`}>Данные для раскроя</h4>
                    <p>Оригинальное лекало и параметры этой вещи</p>
                </div>
            </header>
            <dl className={styles.cuttingGrid}>
                <div>
                    <dt>Код лекала</dt>
                    <dd>{cutting?.pattern_code || '—'}</dd>
                </div>
                <div>
                    <dt>Ткань</dt>
                    <dd>
                        {fabric
                            ? `${fabric.code} · ${fabric.name} · ${fabric.color}`
                            : '—'}
                    </dd>
                </div>
                <div data-empty={!cutting?.fabric_location}>
                    <dt>
                        <PiMapPinLine aria-hidden /> Где ткань
                    </dt>
                    <dd>{cutting?.fabric_location || '—'}</dd>
                </div>
                <div>
                    <dt>
                        <PiRuler aria-hidden /> Ширина спинки
                    </dt>
                    <dd>{centimeters(cutting?.back_width_cm ?? null)}</dd>
                </div>
                <div>
                    <dt>Длина изделия</dt>
                    <dd>{centimeters(cutting?.garment_length_cm ?? null)}</dd>
                </div>
                <div>
                    <dt>Рукав</dt>
                    <dd>
                        {cutting?.sleeve_variant === 'height'
                            ? 'По росту'
                            : 'Стандартный'}
                    </dd>
                </div>
                <div>
                    <dt>DTF</dt>
                    <dd>{cutting?.has_dtf ? 'Есть' : 'Нет'}</dd>
                </div>
            </dl>
        </section>
    );
}
