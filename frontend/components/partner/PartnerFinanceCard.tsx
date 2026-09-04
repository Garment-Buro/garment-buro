import { PiArrowRight, PiWallet } from 'react-icons/pi';

import {
    calculatePendingPartnerBalance,
    formatPartnerMoney,
} from '@/lib/partners/format';
import type { PartnerDashboard } from '@/lib/partners/types';

import styles from './PartnerDashboard.module.css';

type PartnerFinanceCardProps = {
    dashboard: PartnerDashboard;
    hasRequisites: boolean;
    payoutAmount: string;
    payoutPending: boolean;
    payoutOpen: boolean;
    onPayoutAmountChange: (value: string) => void;
    onPayoutOpen: () => void;
    onPayoutClose: () => void;
    onPayoutSubmit: () => void;
    onRequisitesRequired: () => void;
};

export const PartnerFinanceCard = ({
    dashboard,
    hasRequisites,
    payoutAmount,
    payoutPending,
    payoutOpen,
    onPayoutAmountChange,
    onPayoutOpen,
    onPayoutClose,
    onPayoutSubmit,
    onRequisitesRequired,
}: PartnerFinanceCardProps) => {
    const pendingBalance = calculatePendingPartnerBalance(dashboard);
    const available = Number(dashboard.available);

    return (
        <section className={styles.financeCard} aria-labelledby="partner-finance-title">
            <div className={styles.financeTop}>
                <div>
                    <p className={styles.financeLabel} id="partner-finance-title">Доступно к выводу</p>
                    <p className={styles.balance}>{formatPartnerMoney(dashboard.available)}</p>
                </div>
                <span className={styles.walletIcon} aria-hidden="true">
                    <PiWallet size={24} />
                </span>
            </div>

            <dl className={styles.metricGrid}>
                <div className={styles.metric}>
                    <dt>Заказы</dt>
                    <dd>{dashboard.orders.toLocaleString('ru-RU')}</dd>
                </div>
                <div className={styles.metric}>
                    <dt>Начислено</dt>
                    <dd>{formatPartnerMoney(dashboard.earned)}</dd>
                </div>
                <div className={styles.metric}>
                    <dt>В обработке</dt>
                    <dd>{formatPartnerMoney(pendingBalance)}</dd>
                </div>
                <div className={styles.metric}>
                    <dt>Выплачено</dt>
                    <dd>{formatPartnerMoney(dashboard.paid)}</dd>
                </div>
            </dl>

            {!payoutOpen && (
                <button
                    type="button"
                    className={styles.primaryButton}
                    disabled={available <= 0}
                    onClick={hasRequisites ? onPayoutOpen : onRequisitesRequired}
                >
                    {available > 0 ? (
                        <>
                            {hasRequisites ? 'Вывести деньги' : 'Заполнить реквизиты для вывода'}
                            <PiArrowRight size={20} aria-hidden="true" />
                        </>
                    ) : 'Нет средств для вывода'}
                </button>
            )}

            {payoutOpen && (
                <form
                    className={styles.payoutForm}
                    onSubmit={event => {
                        event.preventDefault();
                        onPayoutSubmit();
                    }}
                >
                    <label className={styles.field}>
                        <span>Сумма выплаты</span>
                        <input
                            type="number"
                            min="1"
                            max={available}
                            step="0.01"
                            inputMode="decimal"
                            required
                            value={payoutAmount}
                            onChange={event => onPayoutAmountChange(event.target.value)}
                            placeholder="Введите сумму"
                        />
                    </label>
                    <p className={styles.payoutHint}>
                        После отправки заявка появится в истории выплат.
                    </p>
                    <div className={styles.formActions}>
                        <button
                            type="submit"
                            className={styles.primaryButton}
                            disabled={payoutPending || !payoutAmount || Number(payoutAmount) <= 0}
                        >
                            {payoutPending ? 'Отправляем заявку…' : 'Подтвердить вывод'}
                        </button>
                        <button
                            type="button"
                            className={styles.secondaryButton}
                            disabled={payoutPending}
                            onClick={onPayoutClose}
                        >
                            Отмена
                        </button>
                    </div>
                </form>
            )}
        </section>
    );
};
