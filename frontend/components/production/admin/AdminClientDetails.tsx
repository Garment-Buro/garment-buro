'use client';
import { type KeyboardEvent as ReactKeyboardEvent, useEffect, useState } from 'react';
import {
    PiChatCircle,
    PiCheckCircle,
    PiEnvelope,
    PiMapPin,
    PiPackage,
    PiPhone,
    PiPlusCircle,
    PiUserCircle,
    PiX,
} from 'react-icons/pi';
import { CreateTicket } from '@/components/support/CreateTicket';
import { useAdminResource } from '@/hooks/production/useAdminResource';
import {
    type AdminClient,
    type AdminClientDetail,
    date,
    money,
    priorityLabels,
    statusLabels,
} from '@/lib/production/adminTypes';
import styles from './ProductionAdmin.module.css';

type ClientTab = 'profile' | 'orders' | 'tickets' | 'create';

export function AdminClientDetails({
    client,
    onOrder,
    onTicket,
    onClose,
}: {
    client: AdminClient;
    onOrder: (id: number) => void;
    onTicket: (id: number) => void;
    onClose: () => void;
}) {
    const [activeTab, setActiveTab] = useState<ClientTab>('profile');
    const { data, loading, error } = useAdminResource<AdminClientDetail>(
        `clients/detail?key=${encodeURIComponent(client.key)}`,
    );
    useEffect(() => {
        const closeOnEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', closeOnEscape);
        return () => window.removeEventListener('keydown', closeOnEscape);
    }, [onClose]);

    const canCreateTicket = Boolean(data && client.user_id);
    const tabs: {
        id: ClientTab;
        label: string;
        count?: number;
        icon: typeof PiUserCircle;
    }[] = [
        { id: 'profile', label: 'Данные', icon: PiUserCircle },
        { id: 'orders', label: 'Заказы', count: data?.orders.length, icon: PiPackage },
        {
            id: 'tickets',
            label: 'Обращения',
            count: data?.tickets.length,
            icon: PiChatCircle,
        },
        ...(canCreateTicket
            ? [{ id: 'create' as const, label: 'Новый тикет', icon: PiPlusCircle }]
            : []),
    ];

    const selectAdjacentTab = (
        event: ReactKeyboardEvent<HTMLButtonElement>,
        direction: -1 | 1,
    ) => {
        const currentIndex = tabs.findIndex((tab) => tab.id === activeTab);
        const nextIndex = (currentIndex + direction + tabs.length) % tabs.length;
        setActiveTab(tabs[nextIndex].id);
        const buttons = event.currentTarget.parentElement?.querySelectorAll('button');
        (buttons?.[nextIndex] as HTMLButtonElement | undefined)?.focus();
    };

    return (
        <div
            className={styles.modalBackdrop}
            role="presentation"
            onMouseDown={(event) => {
                if (event.target === event.currentTarget) onClose();
            }}
        >
            <section
                className={styles.clientDialog}
                role="dialog"
                aria-modal="true"
                aria-labelledby="client-details-title"
            >
                <div className={styles.dialogHeading}>
                    <div>
                        <span className={styles.eyebrow}>КЛИЕНТ</span>
                        <h2 id="client-details-title">
                            {client.name || 'Имя не указано'}
                        </h2>
                    </div>
                    <button
                        type="button"
                        className={styles.iconButton}
                        aria-label="Закрыть данные клиента"
                        title="Закрыть"
                        onClick={onClose}
                    >
                        <PiX aria-hidden />
                    </button>
                </div>
                <div
                    className={styles.clientTabs}
                    role="tablist"
                    aria-label="Данные клиента"
                >
                    {tabs.map((tab) => {
                        const Icon = tab.icon;
                        return (
                            <button
                                type="button"
                                role="tab"
                                id={`client-tab-${tab.id}`}
                                aria-controls={`client-panel-${tab.id}`}
                                aria-selected={activeTab === tab.id}
                                tabIndex={activeTab === tab.id ? 0 : -1}
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                onKeyDown={(event) => {
                                    if (event.key === 'ArrowLeft') {
                                        event.preventDefault();
                                        selectAdjacentTab(event, -1);
                                    }
                                    if (event.key === 'ArrowRight') {
                                        event.preventDefault();
                                        selectAdjacentTab(event, 1);
                                    }
                                }}
                            >
                                <Icon aria-hidden />
                                <span>{tab.label}</span>
                                {tab.count !== undefined && <small>{tab.count}</small>}
                            </button>
                        );
                    })}
                </div>
                <div className={styles.clientTabContent}>
                    {loading && (
                        <div className={styles.clientHistorySkeleton} role="status">
                            <span />
                            <span />
                            <span className={styles.srOnly}>
                                Загружаем историю клиента
                            </span>
                        </div>
                    )}
                    {error && (
                        <p role="alert" className={styles.error}>
                            {error}
                        </p>
                    )}
                    {data && activeTab === 'profile' && (
                        <div
                            role="tabpanel"
                            id="client-panel-profile"
                            aria-labelledby="client-tab-profile"
                        >
                            <div className={styles.clientContactList}>
                                <p>
                                    <PiUserCircle aria-hidden />
                                    <span>
                                        <small>Тип клиента</small>
                                        <strong>
                                            {client.user_id
                                                ? `Аккаунт №${client.user_id}`
                                                : 'Гостевые заказы'}
                                        </strong>
                                    </span>
                                </p>
                                <p>
                                    <PiEnvelope aria-hidden />
                                    <span>
                                        <small>Почта</small>
                                        <strong>
                                            {data.account?.email ||
                                                data.email ||
                                                client.email ||
                                                'Не указана'}
                                        </strong>
                                    </span>
                                </p>
                                <p>
                                    <PiPhone aria-hidden />
                                    <span>
                                        <small>Телефон</small>
                                        <strong>
                                            {data.account?.phone ||
                                                data.phone ||
                                                client.phone ||
                                                'Не указан'}
                                        </strong>
                                    </span>
                                </p>
                            </div>
                            <dl className={styles.clientTotals}>
                                <div>
                                    <dt>Заказов</dt>
                                    <dd>{client.orders_count}</dd>
                                </div>
                                <div>
                                    <dt>Сумма заказов</dt>
                                    <dd>{money(client.orders_total)}</dd>
                                </div>
                                <div>
                                    <dt>Оплачено</dt>
                                    <dd>{money(client.paid_orders_total)}</dd>
                                </div>
                            </dl>
                        <section className={styles.clientSection}>
                            <div className={styles.orderSectionHeading}>
                                <PiUserCircle aria-hidden />
                                <div>
                                    <h3>Данные клиента</h3>
                                    <small>
                                        Профиль и данные последней доставки
                                    </small>
                                </div>
                            </div>
                            <dl className={styles.clientProfileGrid}>
                                <div>
                                    <dt>Регистрация</dt>
                                    <dd>
                                        {data.account
                                            ? date(data.account.registered_at)
                                            : 'Без аккаунта'}
                                    </dd>
                                </div>
                                <div>
                                    <dt>Почта</dt>
                                    <dd>
                                        {data.account
                                            ? data.account.email_verified
                                                ? 'Подтверждена'
                                                : 'Не подтверждена'
                                            : 'Нет аккаунта'}
                                    </dd>
                                </div>
                                <div>
                                    <dt>Имя пользователя</dt>
                                    <dd>
                                        {data.account?.username || 'Не указано'}
                                    </dd>
                                </div>
                                <div>
                                    <dt>Дата рождения</dt>
                                    <dd>
                                        {data.account?.birth_date || 'Не указана'}
                                    </dd>
                                </div>
                                <div>
                                    <dt>Пол</dt>
                                    <dd>{data.account?.gender || 'Не указан'}</dd>
                                </div>
                                <div>
                                    <dt>Рост и вес</dt>
                                    <dd>
                                        {[
                                            data.account?.height_cm &&
                                                `${Number(data.account.height_cm)} см`,
                                            data.account?.weight_kg &&
                                                `${Number(data.account.weight_kg)} кг`,
                                        ]
                                            .filter(Boolean)
                                            .join(' · ') || 'Не указаны'}
                                    </dd>
                                </div>
                                <div>
                                    <dt>Отчество</dt>
                                    <dd>
                                        {data.recipient.patronymic || 'Не указано'}
                                    </dd>
                                </div>
                                <div>
                                    <dt>Последняя доставка</dt>
                                    <dd>
                                        {[
                                            data.recipient.city,
                                            data.recipient.address,
                                            data.recipient.pickup_point,
                                            data.recipient.delivery_method,
                                        ]
                                            .filter(Boolean)
                                            .join(', ') || 'Не указана'}
                                    </dd>
                                </div>
                            </dl>
                        </section>
                            {data.recipient.city && (
                                <p className={styles.clientLocation}>
                                    <PiMapPin aria-hidden />
                                    Последний город доставки: {data.recipient.city}
                                </p>
                            )}
                        </div>
                    )}
                    {data && activeTab === 'orders' && (
                        <section
                            className={styles.clientSection}
                            role="tabpanel"
                            id="client-panel-orders"
                            aria-labelledby="client-tab-orders"
                        >
                            <div className={styles.orderSectionHeading}>
                                <PiPackage aria-hidden />
                                <div>
                                    <h3>История заказов</h3>
                                    <small>{data.orders.length} записей</small>
                                </div>
                            </div>
                            {data.orders.length ? (
                                <div className={styles.clientHistoryList}>
                                    {data.orders.map((order) => (
                                    <button
                                        type="button"
                                        key={order.id}
                                        onClick={() => onOrder(order.id)}
                                    >
                                        <span className={styles.clientHistoryIcon}>
                                            <PiPackage aria-hidden />
                                        </span>
                                        <span>
                                            <strong>Заказ №{order.id}</strong>
                                            <small>
                                                {date(order.created_at)} ·{' '}
                                                {statusLabels[
                                                    order.workflow_state || order.status
                                                ] || order.status}
                                            </small>
                                            <small>
                                                {[
                                                    order.delivery_city,
                                                    order.delivery_method,
                                                ]
                                                    .filter(Boolean)
                                                    .join(' · ') ||
                                                    'Доставка не указана'}
                                            </small>
                                        </span>
                                        <span className={styles.clientHistoryValue}>
                                            <strong>{money(order.total)}</strong>
                                            <small>
                                                {statusLabels[order.payment_status] ||
                                                    order.payment_status}
                                            </small>
                                        </span>
                                    </button>
                                    ))}
                                </div>
                            ) : (
                                <p className={styles.clientEmptyHistory}>
                                    <PiPackage aria-hidden />
                                    Заказов пока нет
                                </p>
                            )}
                        </section>
                    )}
                    {data && activeTab === 'tickets' && (
                        <section
                            className={styles.clientSection}
                            role="tabpanel"
                            id="client-panel-tickets"
                            aria-labelledby="client-tab-tickets"
                        >
                            <div className={styles.orderSectionHeading}>
                                <PiChatCircle aria-hidden />
                                <div>
                                    <h3>История обращений</h3>
                                    <small>{data.tickets.length} записей</small>
                                </div>
                            </div>
                            {data.tickets.length ? (
                                <div className={styles.clientHistoryList}>
                                    {data.tickets.map((ticket) => (
                                        <button
                                            type="button"
                                            key={ticket.id}
                                            onClick={() => onTicket(ticket.id)}
                                        >
                                            <span className={styles.clientHistoryIcon}>
                                                <PiChatCircle aria-hidden />
                                            </span>
                                            <span>
                                                <strong>{ticket.subject}</strong>
                                                <small>
                                                    Обращение №{ticket.id} ·{' '}
                                                    {date(ticket.created_at)}
                                                </small>
                                                <small>
                                                    {ticket.order_id
                                                        ? `Заказ №${ticket.order_id}`
                                                        : 'Без заказа'}
                                                </small>
                                            </span>
                                            <span className={styles.clientHistoryValue}>
                                                <strong>
                                                    {statusLabels[ticket.status]}
                                                </strong>
                                                <small>
                                                    {priorityLabels[ticket.priority]}
                                                </small>
                                            </span>
                                        </button>
                                    ))}
                                </div>
                            ) : (
                                <p className={styles.clientEmptyHistory}>
                                    <PiCheckCircle aria-hidden />
                                    Обращений пока нет
                                </p>
                            )}
                        </section>
                    )}
                    {data && activeTab === 'create' && canCreateTicket && (
                        <section
                            className={styles.clientSection}
                            role="tabpanel"
                            id="client-panel-create"
                            aria-labelledby="client-tab-create"
                        >
                            <div className={styles.orderSectionHeading}>
                                <PiPlusCircle aria-hidden />
                                <div>
                                    <h3>Новый тикет</h3>
                                    <small>
                                        Сообщение появится в личном кабинете клиента
                                    </small>
                                </div>
                            </div>
                            <CreateTicket
                                admin
                                defaultOpen
                                embedded
                                showToggle={false}
                                customerUserId={client.user_id ?? undefined}
                                orderOptions={data.orders.map((order) => ({
                                    id: order.id,
                                    label: `Заказ №${order.id} · ${date(order.created_at)} · ${money(order.total)}`,
                                }))}
                                onCreated={onTicket}
                            />
                        </section>
                    )}
                </div>
            </section>
        </div>
    );
}
