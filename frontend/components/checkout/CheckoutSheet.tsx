'use client';

import { useEffect, useRef, type ReactNode, type FormEvent } from 'react';
import { createPortal } from 'react-dom';
import styles from './CheckoutSheet.module.css';

export function CheckoutSheet({ title, children, onClose, onSave, busy = false }: {
    title: string; children: ReactNode; onClose: () => void; onSave: () => void; busy?: boolean;
}) {
    const ref = useRef<HTMLDialogElement>(null);
    useEffect(() => {
        const previousFocus = document.activeElement as HTMLElement | null;
        const dialog = ref.current;
        dialog?.showModal();
        return () => { dialog?.close(); previousFocus?.focus(); };
    }, []);
    const submit = (event: FormEvent) => { event.preventDefault(); onSave(); };
    return createPortal(<dialog ref={ref} className={styles.dialog} aria-label={title}
        onTouchStart={event => event.stopPropagation()} onTouchEnd={event => event.stopPropagation()}
        onPointerDown={event => event.stopPropagation()} onClick={event => event.stopPropagation()}
        onWheel={event => event.stopPropagation()}
        onCancel={event => { event.preventDefault(); onClose(); }}>
        <form className={styles.form} onSubmit={submit}>
            <div className={styles.handle} aria-hidden="true" />
            <div className={styles.body}>
                <h2 className={styles.title}>{title}</h2>
                {children}
            </div>
            <div className={styles.actions}>
                <button type="button" onClick={onClose}>Назад</button><span aria-hidden="true" />
                <button type="submit" disabled={busy}>{busy ? 'Сохраняем…' : 'Сохранить'}</button>
            </div>
        </form>
    </dialog>, document.body);
}
