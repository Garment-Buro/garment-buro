'use client';
/* eslint-disable @next/next/no-img-element -- immutable order snapshot */
import { PiImage, PiRuler, PiSparkle } from 'react-icons/pi';
import type { AdminOrderDetail } from '@/lib/production/adminTypes';
import { money } from '@/lib/production/adminTypes';
import { safeImage } from '@/lib/production/workflow';
import styles from './ProductionAdmin.module.css';

type OrderItem = AdminOrderDetail['items'][number];
type UnknownRecord = Record<string, unknown>;

const sideLabels: Record<string, string> = {
    front: 'Перед',
    back: 'Спина',
    left: 'Левый бок',
    right: 'Правый бок',
};

const record = (value: unknown): UnknownRecord =>
    value && typeof value === 'object' && !Array.isArray(value)
        ? (value as UnknownRecord)
        : {};

const text = (value: unknown) =>
    typeof value === 'string' && value.trim() ? value.trim() : null;

const number = (value: unknown) =>
    typeof value === 'number' && Number.isFinite(value) ? value : null;

const centimeters = (value: unknown) => {
    const result = number(value);
    return result === null ? null : `${result.toLocaleString('ru-RU')} см`;
};

export function AdminOrderItem({ item }: { item: OrderItem }) {
    const customization = record(item.customization);
    const fit = record(customization.fit);
    const images = Object.entries(record(customization.modelImages))
        .map(([side, value]) => ({ side, src: safeImage(value) }))
        .filter((image): image is { side: string; src: string } => Boolean(image.src))
        .slice(0, 2);
    const decorations = Array.isArray(customization.decorations)
        ? customization.decorations.map(record)
        : [];
    const selectedSize = text(customization.selectedSize) || item.size;
    const length = centimeters(fit.lengthCm);
    const width = centimeters(fit.widthCm);
    const comment = text(customization.comment);
    const productImage = safeImage(item.image);

    return (
        <article className={styles.orderItemCard}>
            <div className={styles.orderItemHeading}>
                <div className={styles.orderItemIdentity}>
                    {productImage ? (
                        <img src={productImage} alt="" loading="lazy" />
                    ) : (
                        <span aria-hidden>
                            <PiImage />
                        </span>
                    )}
                    <div>
                        <h4>{item.title}</h4>
                        {item.sku && <small>Артикул {item.sku}</small>}
                    </div>
                </div>
                <strong>{money(item.total)}</strong>
            </div>
            <dl className={styles.orderItemFacts}>
                <div>
                    <dt>Количество</dt>
                    <dd>{item.quantity} шт.</dd>
                </div>
                <div>
                    <dt>Размер</dt>
                    <dd>{selectedSize || 'Не указан'}</dd>
                </div>
                <div>
                    <dt>Цвет</dt>
                    <dd>{item.color || 'Не указан'}</dd>
                </div>
                <div>
                    <dt>Цена за единицу</dt>
                    <dd>{money(item.unit_price)}</dd>
                </div>
            </dl>
            {item.customization && (
                <div className={styles.customizationPanel}>
                    <div className={styles.customizationHeading}>
                        <PiSparkle aria-hidden />
                        <div>
                            <strong>Настройки конструктора</strong>
                            <small>
                                {decorations.length
                                    ? `${decorations.length} нанесений`
                                    : 'Без нанесений'}
                            </small>
                        </div>
                    </div>
                    {(length || width) && (
                        <p className={styles.customizationFit}>
                            <PiRuler aria-hidden />
                            {[length && `Длина ${length}`, width && `Ширина ${width}`]
                                .filter(Boolean)
                                .join(' · ')}
                        </p>
                    )}
                    {images.length > 0 && (
                        <div className={styles.customizationImages}>
                            {images.map((image) => (
                                <figure key={image.side}>
                                    <img
                                        src={image.src}
                                        alt={`${item.title}: ${sideLabels[image.side] || image.side}`}
                                        loading="lazy"
                                    />
                                    <figcaption>
                                        {sideLabels[image.side] || image.side}
                                    </figcaption>
                                </figure>
                            ))}
                        </div>
                    )}
                    {decorations.length > 0 && (
                        <ul className={styles.decorationList}>
                            {decorations.map((decoration, index) => {
                                const decorationText = record(decoration.text);
                                const content = text(decorationText.content);
                                const widthCm = centimeters(decoration.widthCm);
                                const heightCm = centimeters(decoration.heightCm);
                                return (
                                    <li key={text(decoration.uid) || index}>
                                        <span>
                                            <strong>
                                                {text(decoration.name) || 'Нанесение'}
                                            </strong>
                                            <small>
                                                {sideLabels[
                                                    text(decoration.view) || 'front'
                                                ] || 'Перед'}
                                                {widthCm && heightCm
                                                    ? ` · ${widthCm} × ${heightCm}`
                                                    : ''}
                                            </small>
                                        </span>
                                        {content && <q>{content}</q>}
                                    </li>
                                );
                            })}
                        </ul>
                    )}
                    {comment && (
                        <p className={styles.customerComment}>
                            <strong>Комментарий клиента</strong>
                            <span>{comment}</span>
                        </p>
                    )}
                </div>
            )}
        </article>
    );
}
