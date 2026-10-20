'use client';

import { useEffect, useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

import styles from './ServiceCatalogSheet.module.css';

export function ServiceCatalogSheet({ title, children, headerAction, onClose, className = '' }: {
    title: string; children: ReactNode; headerAction?: ReactNode; onClose: () => void; className?: string;
}) {
    const titleId = useId();
    const ref = useRef<HTMLDialogElement>(null);
    const pointerStart = useRef<{ x: number; y: number } | null>(null);
    useEffect(() => {
        const previousFocus = document.activeElement as HTMLElement | null;
        const dialog = ref.current;
        dialog?.showModal();
        return () => { dialog?.close(); previousFocus?.focus(); };
    }, []);

    return createPortal(<dialog ref={ref} className={`${styles.dialog} ${className}`} aria-labelledby={titleId}
        onCancel={event => { event.preventDefault(); onClose(); }}
        onPointerDown={event => {
            pointerStart.current = event.target === event.currentTarget ? { x: event.clientX, y: event.clientY } : null;
        }}
        onClick={event => {
            if (event.target !== event.currentTarget || !pointerStart.current) return;
            const bounds = event.currentTarget.getBoundingClientRect();
            const { x, y } = pointerStart.current;
            if (x < bounds.left || x > bounds.right || y < bounds.top || y > bounds.bottom) onClose();
        }}>
        <button type="button" className={styles.handle} aria-label={`Закрыть ${title.toLocaleLowerCase('ru')}`} onClick={onClose}
            onPointerDown={event => {
                pointerStart.current = { x: event.clientX, y: event.clientY };
                event.currentTarget.setPointerCapture(event.pointerId);
                event.stopPropagation();
            }}
            onPointerUp={event => {
                if (pointerStart.current && event.clientY - pointerStart.current.y > 40) onClose();
            }} />
        <div className={styles.panel}>
            <div className={styles.header}>
                <h2 id={titleId}>{title}</h2>
                {headerAction}
            </div>
            {children}
        </div>
    </dialog>, document.body);
}
