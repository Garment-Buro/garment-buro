/* eslint-disable @next/next/no-img-element -- immutable order media */
import { safeImage } from '@/lib/production/workflow';
import type { Unit } from '@/lib/production/types';
import styles from './ProductionTerminal.module.css';
const names: Record<string, string> = {
    decorations: 'Нанесения',
    side: 'Сторона',
    front: 'Перед',
    back: 'Спинка',
    left: 'Слева',
    right: 'Справа',
    text: 'Текст',
    fontFamily: 'Шрифт',
    fontSize: 'Размер шрифта',
    color: 'Цвет',
    width: 'Ширина',
    height: 'Высота',
    position: 'Положение',
    rotation: 'Поворот',
    size: 'Размер',
    measurements: 'Мерки',
    comment: 'Комментарий',
    type: 'Тип',
    name: 'Название',
    fit: 'Посадка',
};
function Value({ value, depth = 0 }: { value: unknown; depth?: number }) {
    if (value == null) return <span>Не указано</span>;
    if (depth > 6)
        return <span>Подробная структура доступна в исходном заказе</span>;
    if (typeof value === 'boolean') return <span>{value ? 'Да' : 'Нет'}</span>;
    if (typeof value !== 'object')
        return <span className={styles.break}>{String(value)}</span>;
    if (Array.isArray(value))
        return (
            <ol>
                {value.map((item, index) => (
                    <li key={index}>
                        <Value value={item} depth={depth + 1} />
                    </li>
                ))}
            </ol>
        );
    return (
        <dl className={styles.evidence}>
            {Object.entries(value).map(([key, item]) => (
                <div key={key}>
                    <dt>{names[key] ?? key}</dt>
                    <dd>
                        <Value value={item} depth={depth + 1} />
                    </dd>
                </div>
            ))}
        </dl>
    );
}
export function OrderEvidence({ unit }: { unit: Unit }) {
    const image = safeImage(unit.source.image);
    return (
        <details className={styles.section}>
            <summary>
                Данные заказчика · {unit.source.size} · {unit.source.color}
            </summary>
            {image ? (
                <img
                    className={styles.productImage}
                    src={image}
                    alt={unit.source.title}
                />
            ) : (
                <p className={styles.muted}>
                    В заказе нет фотографии. Используйте закреплённые лекала и
                    спецификацию.
                </p>
            )}
            {unit.source.sku && <p>Артикул: {unit.source.sku}</p>}
            {unit.source.customization ? (
                <Value value={unit.source.customization} />
            ) : (
                <p>Заказ без сохранённой кастомизации.</p>
            )}
        </details>
    );
}
