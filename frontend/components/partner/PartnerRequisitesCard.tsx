import { PiBank, PiCaretDown, PiCheckCircle, PiLockKey } from 'react-icons/pi';

import type { PartnerCabinetViewModel } from '@/hooks/partner/usePartnerCabinet';
import type { PartnerEntityType } from '@/lib/partners/types';

import styles from './PartnerDashboard.module.css';

const ENTITY_OPTIONS: Array<{ id: PartnerEntityType; label: string }> = [
    { id: 'self_employed', label: 'Самозанятый' },
    { id: 'sole_proprietor', label: 'ИП' },
    { id: 'legal_entity', label: 'Компания' },
];

type PartnerRequisitesCardProps = {
    cabinet: PartnerCabinetViewModel;
    open: boolean;
    onToggle: () => void;
};

export const PartnerRequisitesCard = ({
    cabinet,
    open,
    onToggle,
}: PartnerRequisitesCardProps) => {
    const draft = cabinet.requisitesDraft;
    const accountTail = cabinet.requisites?.settlement_account.slice(-4);
    const isLegalEntity = draft.entity_type === 'legal_entity';
    const taxIdLength = isLegalEntity ? 10 : 12;

    return (
        <section className={styles.panel} id="partner-requisites" aria-labelledby="requisites-title">
            <button
                type="button"
                className={styles.summaryButton}
                onClick={onToggle}
                aria-expanded={open}
                aria-controls="partner-requisites-form"
            >
                <div>
                    <p className={styles.sectionEyebrow}>Для перечисления денег</p>
                    <h2 id="requisites-title">Реквизиты</h2>
                </div>
                <PiCaretDown
                    size={20}
                    className={`${styles.summaryIcon} ${open ? styles.summaryIconOpen : ''}`}
                    aria-hidden="true"
                />
            </button>

            {!open && cabinet.requisites && (
                <div className={styles.requisitesSummary}>
                    <span className={styles.requisitesSummaryIcon} aria-hidden="true">
                        <PiCheckCircle size={22} />
                    </span>
                    <div>
                        <p className={styles.landingTitle}>{cabinet.requisites.recipient_name}</p>
                        <p className={styles.landingUrl}>
                            {cabinet.requisites.bank_name}, счёт •••• {accountTail}
                        </p>
                    </div>
                </div>
            )}

            {!open && !cabinet.requisites && (
                <p className={styles.emptyText}>
                    Заполните реквизиты, чтобы отправлять заявки на выплату.
                </p>
            )}

            {open && (
                <form
                    id="partner-requisites-form"
                    className={styles.requisitesForm}
                    onSubmit={event => {
                        event.preventDefault();
                        void cabinet.saveRequisites();
                    }}
                >
                    <div className={styles.entitySelector} aria-label="Тип получателя">
                        {ENTITY_OPTIONS.map(option => (
                            <button
                                key={option.id}
                                type="button"
                                className={`${styles.entityOption} ${draft.entity_type === option.id ? styles.entityOptionActive : ''}`}
                                onClick={() => cabinet.setEntityType(option.id)}
                                aria-pressed={draft.entity_type === option.id}
                            >
                                {option.label}
                            </button>
                        ))}
                    </div>

                    <div className={styles.fieldGrid}>
                        <label className={`${styles.field} ${styles.fullWidth}`}>
                            <span>{isLegalEntity ? 'Название организации' : 'Получатель'}</span>
                            <input
                                type="text"
                                autoComplete="organization"
                                required
                                minLength={2}
                                maxLength={255}
                                value={draft.recipient_name}
                                onChange={event => cabinet.setRequisitesField('recipient_name', event.target.value)}
                                placeholder={isLegalEntity ? 'ООО «Название»' : 'Фамилия Имя Отчество'}
                            />
                        </label>

                        <label className={styles.field}>
                            <span>ИНН</span>
                            <input
                                type="text"
                                inputMode="numeric"
                                autoComplete="off"
                                required
                                minLength={taxIdLength}
                                maxLength={taxIdLength}
                                pattern={`\\d{${taxIdLength}}`}
                                value={draft.tax_id}
                                onChange={event => cabinet.setRequisitesField('tax_id', event.target.value.replace(/\D/g, ''))}
                                placeholder={isLegalEntity ? '10 цифр' : '12 цифр'}
                            />
                        </label>

                        {isLegalEntity && (
                            <label className={styles.field}>
                                <span>КПП</span>
                                <input
                                    type="text"
                                    inputMode="numeric"
                                    autoComplete="off"
                                    required
                                    minLength={9}
                                    maxLength={9}
                                    pattern="\d{9}"
                                    value={draft.kpp ?? ''}
                                    onChange={event => cabinet.setRequisitesField('kpp', event.target.value.replace(/\D/g, ''))}
                                    placeholder="9 цифр"
                                />
                            </label>
                        )}

                        <label className={`${styles.field} ${styles.fullWidth}`}>
                            <span>Банк</span>
                            <input
                                type="text"
                                autoComplete="off"
                                required
                                minLength={2}
                                maxLength={255}
                                value={draft.bank_name}
                                onChange={event => cabinet.setRequisitesField('bank_name', event.target.value)}
                                placeholder="Название банка"
                            />
                        </label>

                        <label className={styles.field}>
                            <span>БИК</span>
                            <input
                                type="text"
                                inputMode="numeric"
                                autoComplete="off"
                                required
                                minLength={9}
                                maxLength={9}
                                pattern="\d{9}"
                                value={draft.bic}
                                onChange={event => cabinet.setRequisitesField('bic', event.target.value.replace(/\D/g, ''))}
                                placeholder="9 цифр"
                            />
                        </label>

                        <label className={styles.field}>
                            <span>Корреспондентский счёт</span>
                            <input
                                type="text"
                                inputMode="numeric"
                                autoComplete="off"
                                required
                                minLength={20}
                                maxLength={20}
                                pattern="\d{20}"
                                value={draft.correspondent_account}
                                onChange={event => cabinet.setRequisitesField('correspondent_account', event.target.value.replace(/\D/g, ''))}
                                placeholder="20 цифр"
                            />
                        </label>

                        <label className={`${styles.field} ${styles.fullWidth}`}>
                            <span>Расчётный счёт</span>
                            <input
                                type="text"
                                inputMode="numeric"
                                autoComplete="off"
                                required
                                minLength={20}
                                maxLength={20}
                                pattern="\d{20}"
                                value={draft.settlement_account}
                                onChange={event => cabinet.setRequisitesField('settlement_account', event.target.value.replace(/\D/g, ''))}
                                placeholder="20 цифр"
                            />
                        </label>
                    </div>

                    <p className={styles.helperText}>
                        <PiLockKey size={16} aria-hidden="true" />{' '}
                        Банковские данные хранятся в зашифрованном виде.
                    </p>

                    <button
                        type="submit"
                        className={styles.primaryButton}
                        disabled={cabinet.requisitesPending}
                    >
                        <PiBank size={20} aria-hidden="true" />
                        {cabinet.requisitesPending ? 'Сохраняем…' : 'Сохранить реквизиты'}
                    </button>
                </form>
            )}
        </section>
    );
};
