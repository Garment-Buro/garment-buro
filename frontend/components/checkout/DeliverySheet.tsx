'use client';

import Image from 'next/image';
import { useCallback, useState } from 'react';
import type { CartDeliveryMethod } from '@/lib/cart/actionTypes';
import type { CourierAddress } from '@/lib/checkout/contact';
import { validCourierAddress } from '@/lib/checkout/contact';
import { getOfficeAddress } from '@/lib/cdek/utils/cdek';
import { useCheckoutDetailsStore } from '@/store/checkoutDetailsStore';
import { usePickupDirectory } from '@/hooks/checkout/usePickupDirectory';
import { CdekYandexMap } from '@/components/cdek/CdekYandexMap';
import { CheckoutSheet } from './CheckoutSheet';
import styles from './CheckoutSheet.module.css';

const courierFields: { key: keyof CourierAddress; label: string; required?: boolean; complete?: string }[] = [
    { key: 'city', label: 'Город', required: true, complete: 'address-level2' },
    { key: 'street', label: 'Улица', required: true, complete: 'address-line1' },
    { key: 'house', label: 'Дом и корпус', required: true },
    { key: 'apartment', label: 'Квартира или офис', complete: 'address-line2' },
    { key: 'entrance', label: 'Подъезд' }, { key: 'floor', label: 'Этаж' },
    { key: 'intercom', label: 'Домофон' }, { key: 'comment', label: 'Комментарий курьеру' },
];

export function DeliverySheet({ method, onSave, onClose }: {
    method: CartDeliveryMethod; onSave: (method: CartDeliveryMethod) => void; onClose: () => void;
}) {
    const details = useCheckoutDetailsStore();
    const [tab, setTab] = useState(method);
    const [courier, setCourier] = useState(details.courier);
    const [selected, setSelected] = useState(details.point);
    const [query, setQuery] = useState(details.point?.location?.city || '');
    const [offset, setOffset] = useState(0);
    const [validation, setValidation] = useState('');
    const { page, loading, error, retry } = usePickupDirectory(query, offset, tab === 'pickup');
    const selectPoint = useCallback((code: string) => {
        const point = page?.points.find(value => value.code === code);
        if (point) { setSelected(point); setValidation(''); }
    }, [page]);
    const save = () => {
        if (tab === 'pickup') {
            if (!selected) { setValidation('Выберите пункт на карте или в списке.'); return; }
            details.setPoint(selected);
        } else {
            if (!validCourierAddress(courier)) { setValidation('Укажите город, улицу и дом.'); return; }
            details.setCourier(courier);
        }
        onSave(tab); onClose();
    };
    return <CheckoutSheet title="Список адресов" onClose={onClose} onSave={save}>
        <div className={styles.tabs} role="tablist" aria-label="Способ доставки">
            <button type="button" role="tab" aria-selected={tab === 'pickup'} onClick={() => { setTab('pickup'); setValidation(''); }}>Пункт самовывоза</button>
            <button type="button" role="tab" aria-selected={tab === 'courier'} onClick={() => { setTab('courier'); setValidation(''); }}>Доставка курьером</button>
        </div>
        {tab === 'pickup' ? <>
            <label className={`${styles.field} ${styles.search}`}>Найти пункт СДЭК
                <input type="search" maxLength={200} placeholder="Город, улица или код пункта" value={query} onChange={event => { setQuery(event.target.value); setOffset(0); }} />
            </label>
            {loading && !page ? <div className={styles.skeleton} aria-label="Загружаем пункты" /> : <CdekYandexMap offices={page?.points || []} selectedCode={selected?.code || ''} searchCenter={null} selectedAddressLabel="" onSelect={selectPoint} />}
            {error && <div role="alert"><p className={styles.error}>{error}</p><button type="button" onClick={retry}>Повторить загрузку</button></div>}
            {selected && <p className={styles.note}>Выбрано: {selected.location?.city}, {getOfficeAddress(selected)}</p>}
            <div className={styles.points} role="radiogroup" aria-label="Пункты СДЭК" aria-busy={loading}>
                {page?.points.map(point => <button key={point.code} type="button" role="radio" aria-checked={selected?.code === point.code} className={styles.point} onClick={() => selectPoint(point.code)}>
                    <span className={styles.radio} aria-hidden="true" /><span className={styles.pointText}>
                        <Image src="/cdek icon.svg" alt="СДЭК" width={52} height={16} />
                        <span>{point.location?.city}, {getOfficeAddress(point)}</span>
                        <span className={styles.note}>{point.work_time || 'Режим работы уточняется'} · {point.code}</span>
                    </span>
                </button>)}
            </div>
            {page && !loading && page.total === 0 && <p className={styles.note}>Пункты не найдены. Попробуйте указать только город или улицу.</p>}
            {page && page.total > 50 && <div className={styles.tabs}>
                <button type="button" disabled={!offset || loading} onClick={() => setOffset(value => Math.max(0, value - 50))}>Предыдущие</button>
                <button type="button" disabled={offset + 50 >= page.total || loading} onClick={() => setOffset(value => value + 50)}>Следующие</button>
            </div>}
            {page && <p className={styles.note}>Найдено: {page.total}. Справочник обновлён {new Date(page.updated_at).toLocaleDateString('ru-RU')}.{page.stale ? ' Используется последняя сохранённая версия.' : ''}</p>}
        </> : <div className={styles.fields}>
            {courierFields.map(field => <label className={styles.field} key={field.key}>{field.label}{field.required ? ' *' : ''}
                <input value={courier[field.key]} autoComplete={field.complete} required={field.required} maxLength={field.key === 'comment' ? 500 : 150} onChange={event => setCourier(value => ({ ...value, [field.key]: event.target.value }))} />
            </label>)}
        </div>}
        {validation && <p role="alert" className={styles.error}>{validation}</p>}
    </CheckoutSheet>;
}
