'use client';

import { useState } from 'react';
import { useAuthStore } from '@/store/authStore';
import { useCheckoutDetailsStore } from '@/store/checkoutDetailsStore';
import { validContact, type CheckoutContact } from '@/lib/checkout/contact';
import { CheckoutSheet } from './CheckoutSheet';
import styles from './CheckoutSheet.module.css';

function ContactFields({ value, onChange, section }: { value: CheckoutContact; onChange: (value: CheckoutContact) => void; section: string }) {
    return <fieldset className={styles.fields}>
        <legend className={styles.legend}>{section}</legend>
        <label className={styles.field}>Полное имя (фамилия, имя, отчество)
            <input autoComplete="name" required minLength={2} maxLength={255} value={value.name} placeholder="Ваше полное имя" onChange={event => onChange({ ...value, name: event.target.value })} />
        </label>
        <label className={styles.field}>Телефон
            <input autoComplete="tel" type="tel" required maxLength={64} value={value.phone} placeholder="+7 900 123 45 67" onChange={event => onChange({ ...value, phone: event.target.value })} />
        </label>
        <label className={styles.field}>Почта
            <input autoComplete="email" type="email" required maxLength={320} value={value.email} placeholder="Ваша почта" onChange={event => onChange({ ...value, email: event.target.value })} />
        </label>
    </fieldset>;
}

export function RecipientSheet({ onClose }: { onClose: () => void }) {
    const details = useCheckoutDetailsStore();
    const user = useAuthStore(state => state.user);
    const [buyer, setBuyer] = useState<CheckoutContact>(() => ({
        name: details.buyer.name || [user?.last_name, user?.first_name].filter(Boolean).join(' '),
        email: details.buyer.email || user?.email || '', phone: details.buyer.phone || user?.phone || '',
    }));
    const [recipient, setRecipient] = useState(details.recipient);
    const [same, setSame] = useState(details.recipientIsBuyer);
    const [error, setError] = useState('');
    const save = () => {
        if (!validContact(buyer) || (!same && !validContact(recipient))) {
            setError('Проверьте полное имя, телефон и почту.'); return;
        }
        details.setContacts(buyer, same ? buyer : recipient, same);
        onClose();
    };
    return <CheckoutSheet title="Получатель" onClose={onClose} onSave={save}>
        <ContactFields value={buyer} onChange={setBuyer} section="Ваши данные" />
        <p className={styles.note}>По этой почте создадим личный кабинет. Для входа и просмотра заказов нужно подтвердить почту кодом. Телефон нужен для связи по доставке.</p>
        <label className={`${styles.inlineCheck} my-6`}><input type="checkbox" checked={same} onChange={event => setSame(event.target.checked)} />Получатель — я</label>
        {!same && <ContactFields value={recipient} onChange={setRecipient} section="Данные получателя" />}
        {error && <p role="alert" className={styles.error}>{error}</p>}
    </CheckoutSheet>;
}
