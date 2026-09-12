'use client';
import { useAdminResource } from '@/hooks/production/useAdminResource';
import {
    type AdminOrderDetail,
    date,
    money,
    statusLabels,
} from '@/lib/production/adminTypes';
import styles from './ProductionAdmin.module.css';
import { AdminOrderModeration } from './AdminOrderModeration';

export function AdminOrderDetails({
    id,
    onClose,
}: {
    id: number;
    onClose: () => void;
}) {
    const { data, loading, error, reload } = useAdminResource<AdminOrderDetail>(
        `orders/${id}`,
    );
    return (
        <section
            className={styles.card}
            aria-label={`Заказ ${id}`}
            aria-busy={loading}
        >
            <div className={styles.sectionHeading}>
                <h2>Заказ №{id}</h2>
                <button onClick={onClose}>Закрыть детали</button>
            </div>
            {loading && <p role="status">Загружаем состав заказа…</p>}
            {error && (
                <>
                    <p role="alert" className={styles.error}>
                        {error}
                    </p>
                    <button onClick={reload}>Повторить</button>
                </>
            )}
            {data && (
                <>
                    <AdminOrderModeration order={data} reload={reload} />
                    <p>
                        {data.name || 'Имя не указано'} ·{' '}
                        {data.email || 'Без почты'} ·{' '}
                        {data.phone || 'Без телефона'}
                    </p>
                    <p>
                        {date(data.created_at)} ·{' '}
                        {statusLabels[data.workflow_state || data.status] ||
                            data.status}{' '}
                        · {money(data.total)}
                    </p>
                    <h3>Доставка</h3>
                    <p>
                        {[
                            data.delivery_city,
                            data.delivery_address,
                            data.pickup_point,
                        ]
                            .filter(Boolean)
                            .join(', ') || 'Адрес не сохранён'}
                    </p>
                    <p>
                        {data.delivery_method || 'Способ не указан'} ·{' '}
                        {money(data.delivery_price)}
                    </p>
                    <h3>Состав заказа</h3>
                    {data.items.map((item) => (
                        <article key={item.id} className={styles.item}>
                            <h4>
                                {item.title} · {item.quantity} шт.
                            </h4>
                            <p>
                                {item.size} · {item.color} · {money(item.total)}
                            </p>
                            {item.customization && (
                                <details>
                                    <summary>
                                        Сохранённые параметры конструктора
                                    </summary>
                                    <pre>
                                        {JSON.stringify(
                                            item.customization,
                                            null,
                                            2,
                                        )}
                                    </pre>
                                </details>
                            )}
                        </article>
                    ))}
                </>
            )}
        </section>
    );
}
