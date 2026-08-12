"use client";

import Image from "next/image";

import { AppIcon } from "@/components/icons/AppIcon";
import type { UnfinishedSurfaceViewModel } from "@/hooks/unfinished/useUnfinishedSurface";
import { profileTabs } from "@/lib/unfinished/config/ui";
import type { ProfileOrder } from "@/lib/unfinished/types";
import styles from "./UnfinishedSurface.module.css";

type ProfilePanelProps = {
    surface: UnfinishedSurfaceViewModel;
};

function PaidBadge({ isPaid }: { isPaid: boolean }) {
    return (
        <span className={`${styles.paidBadge} ${isPaid ? styles.paidBadgeActive : ""}`}>
            {isPaid ? "Оплачен" : "Ожидает оплаты"}
        </span>
    );
}

function OrderStatusList({ surface, compact = false }: ProfilePanelProps & { compact?: boolean }) {
    return (
        <div className={`${styles.orderTimeline} ${compact ? styles.orderTimelineCompact : ""}`}>
            {surface.orderStatusFixtures.map((status) => (
                <div className={styles.orderStatusRow} key={status.label}>
                    <span className={`${styles.orderStatusDot} ${status.done ? styles.orderStatusDotDone : ""}`} />
                    <span className={styles.orderStatusText}>{status.label}</span>
                    <span className={styles.orderStatusDate}>{status.date}</span>
                </div>
            ))}
        </div>
    );
}

function OrderSummary({
    order,
    isExpanded,
    onToggle,
}: {
    order: ProfileOrder;
    isExpanded: boolean;
    onToggle: (orderId: string) => void;
}) {
    return (
        <button className={styles.orderSummary} type="button" onClick={() => onToggle(order.id)}>
            <span className={styles.orderSummaryText}>
                <strong>{order.title}</strong>
                <span>{order.date} • {order.total}</span>
            </span>
            <PaidBadge isPaid={order.paid} />
            <span className={`${styles.orderArrow} ${isExpanded ? styles.orderArrowOpen : ""}`} aria-hidden="true" />
        </button>
    );
}

function ExpandedOrder({
    order,
    onCollapse,
    surface,
}: {
    order: ProfileOrder;
    onCollapse: () => void;
    surface: UnfinishedSurfaceViewModel;
}) {
    return (
        <div className={styles.profileOrdersCard}>
            <div className={styles.orderExpandedHeader}>
                <span>
                    <strong>{order.title}</strong>
                    <span>{order.date} • {order.total}</span>
                </span>
                <PaidBadge isPaid={order.paid} />
                <button
                    className={`${styles.orderArrow} ${styles.orderArrowOpen}`}
                    type="button"
                    aria-label="Свернуть заказ"
                    onClick={onCollapse}
                />
            </div>

            <div className={styles.orderReceipt}>
                <span className={styles.profileSectionLabel}>СОСТАВ ЗАКАЗА</span>
                {[1, 2].map((item) => (
                    <div className={styles.orderProductRow} key={item}>
                        <Image src="/mock/hoodie.webp" alt="" width={42} height={42} />
                        <span>
                            <strong>худи на молнии с мехом &quot;Cold Оверсайз&quot;</strong>
                            <span>Цвет: Черный</span>
                            <span>Размер: M</span>
                        </span>
                    </div>
                ))}
                <div className={styles.orderTotals}>
                    <span><span>Сумма товаров</span><strong>5 980 ₽</strong></span>
                    <span><span>Доставка</span><strong>240 ₽</strong></span>
                    <span><span>Итого</span><strong>6 220 ₽</strong></span>
                </div>
            </div>

            <section className={styles.profileInfoBlock}>
                <span className={styles.profileSectionLabel}>ПОЛУЧАТЕЛЬ</span>
                <strong>Иванов Иван</strong>
                <span>+7 900 111 22 33 • ivanov_ivan@gmail.com</span>
                <span>Россия, г. Москва, пункт выдачи СДЭК<br />ул. Беговая, 38/1, 170007</span>
            </section>

            <section className={styles.profileInfoBlock}>
                <span className={styles.profileSectionLabel}>СТАТУС ЗАКАЗА</span>
                <OrderStatusList surface={surface} compact />
            </section>
        </div>
    );
}

function ProfileOrders({ surface }: ProfilePanelProps) {
    const expandedOrder = surface.profileOrderFixtures.find((order) => order.id === surface.expandedOrderId);

    if (expandedOrder) {
        return <ExpandedOrder order={expandedOrder} onCollapse={surface.handleCollapseOrder} surface={surface} />;
    }

    return (
        <div className={`${styles.profileOrdersCard} ${styles.profileOrdersListCard}`}>
            <div className={styles.orderSummaries}>
                {surface.profileOrderFixtures.length === 0 && (
                    <p className={styles.profileEmptyState}>Заказов пока нет.</p>
                )}
                {surface.profileOrderFixtures.map((order) => (
                    <OrderSummary
                        key={order.id}
                        order={order}
                        isExpanded={surface.expandedOrderId === order.id}
                        onToggle={surface.handleToggleOrder}
                    />
                ))}
            </div>
        </div>
    );
}

function ProfileDiscounts({ surface }: ProfilePanelProps) {
    return (
        <div className={styles.discountList}>
            {surface.discountCardFixtures.length === 0 && (
                <p className={styles.profileEmptyState}>Скидок пока нет.</p>
            )}
            {surface.discountCardFixtures.map((discount) => (
                <article
                    className={`${styles.discountCard} ${discount.locked ? styles.discountCardLocked : ""}`}
                    key={`${discount.value}-${discount.title}`}
                    style={{ backgroundImage: "url('/discount_bg.webp')" }}
                >
                    <div className={styles.discountValue}>{discount.value}</div>
                    <div className={styles.discountDetails}>
                        <strong>{discount.title}</strong>
                        <span className={styles.discountMeta}>
                            <span>{discount.meta}</span>
                            {discount.suffix && <span>{discount.suffix}</span>}
                        </span>
                        {discount.note && <span className={styles.discountNote}>{discount.note}</span>}
                    </div>
                    {discount.locked && (
                        <AppIcon name="discount-lock" width={14} height={14} className={styles.discountLockIcon} />
                    )}
                </article>
            ))}
        </div>
    );
}

function ProfileSettings({ surface }: ProfilePanelProps) {
    if (!surface.isProfileSignedIn) {
        return (
            <div className={styles.profileSettingsCard}>
                <h2>Вход</h2>
                <label className={styles.profileField}>
                    <span>Почта</span>
                    <input
                        type="email"
                        value={surface.loginEmail}
                        autoComplete="email"
                        onChange={(event) => surface.setLoginEmail(event.target.value)}
                    />
                </label>
                <div className={styles.profileCodeSlots} aria-label="Код из письма">
                    {surface.profileCode.map((character, index) => (
                        <input
                            key={index}
                            ref={(input) => {
                                surface.profileCodeInputRefs.current[index] = input;
                            }}
                            type="text"
                            inputMode="numeric"
                            autoComplete={index === 0 ? "one-time-code" : "off"}
                            value={character}
                            maxLength={1}
                            aria-label={`Цифра кода ${index + 1}`}
                            onChange={(event) => surface.handleProfileCodeChange(index, event.target.value)}
                            onKeyDown={(event) => surface.handleProfileCodeKeyDown(index, event)}
                        />
                    ))}
                </div>
                {surface.isCodeRequested && (
                    <button className={styles.profileResendButton} type="button">Отправить снова (0:59)</button>
                )}
                <button className={styles.profilePrimaryButton} type="button" onClick={surface.handleProfileLoginAction}>
                    {surface.isCodeRequested ? "ВОЙТИ" : "ПОЛУЧИТЬ КОД"}
                </button>
                <p className={styles.profileConsentText}>
                    Нажимая на кнопку, вы подтверждаете, что ознакомлены
                    с Соглашением о конфиденциальности и разрешаете
                    использовать персональные данные
                </p>
            </div>
        );
    }

    return (
        <div className={styles.profileSettingsCard}>
            <span className={styles.profileSectionLabel}>ЛИЧНАЯ ИНФОРМАЦИЯ</span>
            <label className={styles.profileField}>
                <span>Имя профиля</span>
                <input value={surface.profileName} autoComplete="name" onChange={(event) => surface.setProfileName(event.target.value)} />
                <span className={styles.profileEditMark} aria-hidden="true">/</span>
            </label>
            <div className={styles.profileField}>
                <span>Пол</span>
                <button className={styles.profileSelect} type="button" onClick={() => surface.setIsGenderOpen((isOpen) => !isOpen)}>
                    {surface.profileGender}
                    <span aria-hidden="true">⌄</span>
                </button>
                {surface.isGenderOpen && (
                    <div className={styles.profileGenderMenu}>
                        {["Мужской", "Женский", "Не выбран"].map((gender) => (
                            <button
                                key={gender}
                                type="button"
                                onClick={() => {
                                    surface.setProfileGender(gender);
                                    surface.setIsGenderOpen(false);
                                }}
                            >
                                {gender}
                            </button>
                        ))}
                    </div>
                )}
            </div>

            <span className={styles.profileSectionLabel}>КОНТАКТЫ</span>
            <label className={styles.profileField}>
                <span>Телефон</span>
                <input type="tel" value={surface.profilePhone} autoComplete="tel" onChange={(event) => surface.setProfilePhone(event.target.value)} />
            </label>
            <label className={styles.profileField}>
                <span>Почта</span>
                <input type="email" value={surface.profileEmail} autoComplete="email" onChange={(event) => surface.setProfileEmail(event.target.value)} />
                <span className={styles.profileEditMark} aria-hidden="true">/</span>
            </label>

            <button className={styles.profileDeleteAccount} type="button">Удалить аккаунт</button>
        </div>
    );
}

function ProfileSupport() {
    return (
        <div className={styles.profileSettingsCard}>
            <span className={styles.profileSectionLabel}>ПОДДЕРЖКА</span>
            <h2>Напишите нам</h2>
            <p className={styles.profileSupportText}>Ответим на вопросы по заказу, доставке и настройкам профиля.</p>
            <button className={styles.profilePrimaryButton} type="button">ОТПРАВИТЬ</button>
        </div>
    );
}

function ProfileContent({ surface }: ProfilePanelProps) {
    if (surface.activeProfileTab === "discounts") return <ProfileDiscounts surface={surface} />;
    if (surface.activeProfileTab === "orders") return <ProfileOrders surface={surface} />;
    if (surface.activeProfileTab === "support") return <ProfileSupport />;
    return <ProfileSettings surface={surface} />;
}

export function ProfilePanel({ surface }: ProfilePanelProps) {
    return (
        <div className={styles.profileContentShell}>
            <nav className={styles.profileTopTabs} aria-label="Разделы профиля">
                {profileTabs.map((item) => (
                    <button
                        className={`${styles.surfaceButton} ${styles.profileTopTab} ${surface.activeProfileTab === item.id ? styles.profileTopTabActive : ""}`}
                        key={item.id}
                        type="button"
                        onClick={() => surface.handleSelectProfileTab(item.id)}
                    >
                        {item.icon ? (
                            <Image src={item.icon} alt="" width={28} height={20} className={styles.profileDiscountIcon} />
                        ) : item.label}
                    </button>
                ))}
            </nav>

            <div className={styles.profileCard}>
                <ProfileContent surface={surface} />
            </div>
        </div>
    );
}
