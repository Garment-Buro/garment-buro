import { PiBank, PiCaretDown, PiCheckCircle, PiLockKey } from 'react-icons/pi';

import { usePartnerRequisites } from '@/hooks/partner/usePartnerRequisites';
import { emptyRequisitesDraft } from '@/lib/partners/requisitesEditor';
import type { PartnerEntityType } from '@/lib/partners/types';

import styles from './PartnerDashboard.module.css';

const ENTITY_OPTIONS: Array<{ id: PartnerEntityType; label: string }> = [
    { id: 'self_employed', label: 'Самозанятый' },
    { id: 'sole_proprietor', label: 'ИП' },
    { id: 'legal_entity', label: 'Компания' },
];

type PartnerRequisitesCardProps = {
    hasRequisites: boolean;
    onSaved: () => void;
    open: boolean;
    onToggle: () => void;
};

export const PartnerRequisitesCard = ({
    hasRequisites,
    onSaved,
    open,
    onToggle,
}: PartnerRequisitesCardProps) => {
    const editor = usePartnerRequisites(open, onSaved);
    const state = editor.state;
    const draft = state?.draft ?? emptyRequisitesDraft();
    const accountTail = state?.record?.settlement_account.slice(-4);
    const saving = state?.status === 'saving';
    const loading = state?.status === 'loading';
    const locked = saving || loading || state?.conflict;
    const isLegalEntity = draft.entity_type === 'legal_entity';
    const taxIdLength = isLegalEntity ? 10 : 12;

    return (
        <section className={styles.panel} id="partner-requisites" aria-labelledby="requisites-title">
            <button
                type="button"
                className={styles.summaryButton}
                onClick={onToggle}
                disabled={saving}
                aria-expanded={open}
                aria-controls="partner-requisites-content"
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

            {!open && state?.record && (
                <div className={styles.requisitesSummary}>
                    <span className={styles.requisitesSummaryIcon} aria-hidden="true">
                        <PiCheckCircle size={22} />
                    </span>
                    <div>
                        <p className={styles.landingTitle}>{state.record.recipient_name}</p>
                        <p className={styles.landingUrl}>
                            {state.record.bank_name}, счёт •••• {accountTail}
                        </p>
                    </div>
                </div>
            )}

            {!open && !state?.record && !hasRequisites && (
                <p className={styles.emptyText}>
                    Заполните реквизиты, чтобы отправлять заявки на выплату.
                </p>
            )}

            {!open && !state?.record && hasRequisites && <p className={styles.emptyText}>Реквизиты сохранены.</p>}
            <div id="partner-requisites-content" hidden={!open}>
            {open && !state?.loaded && !state?.error && <p role="status">Загружаем реквизиты…</p>}
            {open && Boolean(state?.error) && !state?.conflict && <p role="alert" className={styles.error}>
                {state?.reloadFailed ? 'Не удалось загрузить актуальные реквизиты. Ваш черновик сохранён.' : state?.loaded ? 'Не удалось сохранить реквизиты. Проверьте поля и повторите.' : 'Не удалось загрузить реквизиты.'}{' '}
                {!state?.loaded && <button type="button" className={styles.secondaryButton} onClick={() => void editor.retry()}>Повторить загрузку реквизитов</button>}
            </p>}
            {open && state?.conflict && <p role="alert" className={styles.error}>
                Реквизиты изменились в другой вкладке. Ваш черновик сохранён, повторное сохранение остановлено.
                {state.reloadFailed && ' Не удалось загрузить актуальные реквизиты. Попробуйте ещё раз.'}
            </p>}
            {open && state?.loaded && <details>
                <summary>Загрузить актуальные реквизиты</summary>
                <p className={styles.helperText}>Текущий черновик будет заменён данными с сервера после успешной загрузки.</p>
                <button type="button" className={styles.secondaryButton} disabled={saving || loading} onClick={() => void editor.reload()}>
                    {loading ? 'Загружаем…' : 'Заменить черновик актуальной версией'}
                </button>
            </details>}
            {open && state?.saved && <p role="status" className={styles.notice}>Реквизиты сохранены.</p>}
            {open && state?.loaded && (
                <form
                    id="partner-requisites-form"
                    className={styles.requisitesForm}
                    onSubmit={event => {
                        event.preventDefault();
                        void editor.save();
                    }}
                >
                    <fieldset className={styles.requisitesFields} disabled={locked}>
                    <div className={styles.entitySelector} aria-label="Тип получателя">
                        {ENTITY_OPTIONS.map(option => (
                            <button
                                key={option.id}
                                type="button"
                                className={`${styles.entityOption} ${draft.entity_type === option.id ? styles.entityOptionActive : ''}`}
                                onClick={() => editor.setEntityType(option.id)}
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
                                onChange={event => editor.setField('recipient_name', event.target.value)}
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
                                onChange={event => editor.setField('tax_id', event.target.value.replace(/\D/g, ''))}
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
                                    onChange={event => editor.setField('kpp', event.target.value.replace(/\D/g, ''))}
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
                                onChange={event => editor.setField('bank_name', event.target.value)}
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
                                onChange={event => editor.setField('bic', event.target.value.replace(/\D/g, ''))}
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
                                onChange={event => editor.setField('correspondent_account', event.target.value.replace(/\D/g, ''))}
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
                                onChange={event => editor.setField('settlement_account', event.target.value.replace(/\D/g, ''))}
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
                        disabled={saving}
                    >
                        <PiBank size={20} aria-hidden="true" />
                        {saving ? 'Сохраняем…' : 'Сохранить реквизиты'}
                    </button>
                    </fieldset>
                </form>
            )}
            </div>
        </section>
    );
};
