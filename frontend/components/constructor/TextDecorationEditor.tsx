'use client';

import { useEffect, useRef, useState } from 'react';
import type { TextDecoration, UploadedImage } from '@/lib/constructor/types';
import { DEFAULT_TEXT_DECORATION, renderTextDecoration, TEXT_FONTS } from '@/lib/constructor/utils/textDecoration';
import styles from './TextDecorationEditor.module.css';

type Props = {
    initialValue?: TextDecoration;
    onClose: () => void;
    onSave: (result: UploadedImage & { text: TextDecoration }) => void;
};

export function TextDecorationEditor({ initialValue, onClose, onSave }: Props) {
    const dialogRef = useRef<HTMLDialogElement>(null);
    const [value, setValue] = useState(initialValue || DEFAULT_TEXT_DECORATION);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const font = TEXT_FONTS.find((entry) => entry.id === value.fontId) || TEXT_FONTS[0];

    useEffect(() => { dialogRef.current?.showModal(); }, []);

    const save = async () => {
        if (busy) return;
        setBusy(true);
        setError('');
        try {
            onSave(await renderTextDecoration(value));
            onClose();
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : 'Не удалось сохранить текст.');
            setBusy(false);
        }
    };

    return (
        <dialog ref={dialogRef} className={styles.dialog} onCancel={(event) => { event.preventDefault(); if (!busy) onClose(); }} aria-labelledby="text-editor-title">
            <form onSubmit={(event) => { event.preventDefault(); void save(); }}>
                <header className={styles.header}>
                    <h2 id="text-editor-title">{initialValue ? 'Изменить текст' : 'Добавить текст'}</h2>
                    <button type="button" onClick={onClose} disabled={busy} aria-label="Закрыть редактор текста">×</button>
                </header>
                <label>Текст<textarea autoFocus maxLength={200} rows={3} value={value.content} onChange={(event) => setValue({ ...value, content: event.target.value })} placeholder="Ваша надпись" required /></label>
                <div className={styles.controls}>
                    <label>Шрифт<select value={value.fontId} onChange={(event) => setValue({ ...value, fontId: event.target.value as TextDecoration['fontId'] })}>
                        {TEXT_FONTS.map((entry) => <option key={entry.id} value={entry.id}>{entry.label}</option>)}
                    </select></label>
                    <label>Размер<input aria-label="Размер текста" type="number" min={12} max={120} value={value.fontSize} onChange={(event) => setValue({ ...value, fontSize: Number(event.target.value) })} required /></label>
                    <label>Цвет<input type="color" value={value.color} onInput={(event) => setValue({ ...value, color: event.currentTarget.value })} onChange={(event) => setValue({ ...value, color: event.target.value })} /></label>
                </div>
                <div className={styles.swatches} aria-label="Цвет надписи">
                    {[['#181818', 'Чёрный'], ['#ffffff', 'Белый'], ['#b62929', 'Красный'], ['#033d64', 'Синий']].map(([color, name]) => (
                        <button key={color} type="button" aria-label={name} aria-pressed={value.color === color} onClick={() => setValue({ ...value, color })} style={{ background: color }} />
                    ))}
                </div>
                <div className={styles.preview} aria-label="Предпросмотр надписи" style={{ fontFamily: font.family, fontWeight: font.weight, fontSize: Math.min(32, Math.max(12, value.fontSize)), color: value.color }}>{value.content || 'Ваша надпись'}</div>
                <p className={styles.note}>До 6 строк. На изделии надпись можно перемещать, поворачивать и масштабировать двумя пальцами.</p>
                {error && <p role="alert">{error}</p>}
                <button className={styles.save} type="submit" disabled={busy || !value.content.trim()}>{busy ? 'Сохраняем…' : initialValue ? 'Сохранить' : 'Добавить на изделие'}</button>
            </form>
        </dialog>
    );
}
