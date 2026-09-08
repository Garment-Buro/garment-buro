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
    modelImages: 'Основа изделия (без наложения нанесений)',
    selectedSize: 'Выбранный размер',
    view: 'Сторона изделия',
    widthCm: 'Ширина, см',
    heightCm: 'Высота, см',
    lengthCm: 'Длина, см',
    image: 'Превью нанесения',
    content: 'Содержание',
    fontId: 'Шрифт',
    canvas: 'Рабочая область конструктора',
    garment: 'Габариты изделия',
    scale: 'Масштаб',
};
function Value({
    value,
    depth = 0,
    field = '',
}: {
    value: unknown;
    depth?: number;
    field?: string;
}) {
    if (value == null) return <span>Не указано</span>;
    if (depth > 6)
        return <span>Подробная структура доступна в исходном заказе</span>;
    if (typeof value === 'boolean') return <span>{value ? 'Да' : 'Нет'}</span>;
    if (typeof value === 'string' && value.startsWith('data:'))
        return (
            <span>
                Встроенное превью сохранено в заказе. Для производства закрепите
                отдельный оригинал файла.
            </span>
        );
    if (['image', 'front', 'back'].includes(field) && safeImage(value))
        return (
            <img
                className={styles.productImage}
                src={safeImage(value)!}
                alt={names[field] ?? field}
                loading="lazy"
            />
        );
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
                        <Value value={item} depth={depth + 1} field={key} />
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
