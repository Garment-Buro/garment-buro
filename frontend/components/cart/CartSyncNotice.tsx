'use client';

import {useState} from 'react';
import {useCartStore} from '@/store/cartStore';

/** Shared by the mobile cart and the checkout page. */
export function CartSyncNotice() {
    const failed = useCartStore(state => state.cartSyncError);
    const conflict = useCartStore(state => state.cartSyncConflict);
    const retry = useCartStore(state => state.retryCartSync);
    const resolve = useCartStore(state => state.resolveCartConflict);
    const [busy, setBusy] = useState(false);
    if(!failed && !conflict) return null;
    const act = async (job: () => Promise<void>) => {
        setBusy(true);
        try {await job()} finally {setBusy(false)}
    };
    const buttonClass = 'mt-2 mr-4 underline underline-offset-4 disabled:opacity-50';
    return <div role="alert" className="px-6 py-3 text-sm text-red-800">
        <p>{conflict
            ? 'Корзина изменилась в другой вкладке. Выберите, какой состав использовать.'
            : 'Не удалось синхронизировать корзину. Повторите попытку перед закрытием страницы.'}</p>
        {conflict ? <>
            <button type="button" disabled={busy} onClick={() => void act(() => resolve('server'))} className={buttonClass}>Загрузить серверную корзину</button>
            <button type="button" disabled={busy} onClick={() => void act(() => resolve('local'))} className={buttonClass}>Заменить серверную моей</button>
        </> : <button type="button" disabled={busy} onClick={() => void act(retry)} className={buttonClass}>{busy ? 'Синхронизация…' : 'Повторить синхронизацию'}</button>}
        {busy && conflict && <p role="status">Синхронизация…</p>}
    </div>;
}
