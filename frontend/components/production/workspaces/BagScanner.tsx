'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { productionApi } from '@/lib/api/production';
import { parseBagReference } from '@/lib/production/workspaces';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import styles from './ProductionFlow.module.css';
import { CameraScanner } from './CameraScanner';
import { requestJson } from '@/lib/api/http';
import type { Station } from '@/lib/production/types';

export function BagScanner({
    disabled,
    station,
    onOpen,
}: {
    disabled: boolean;
    station: Station;
    onOpen: (id: number, unit?: number) => void;
}) {
    const run = useProductionAuthStore((s) => s.runAuthenticated);
    const [value, setValue] = useState('');
    const [pending, setPending] = useState(false);
    const [error, setError] = useState('');
    const [camera, setCamera] = useState(false);
    const form = useRef<HTMLFormElement>(null);
    const scanned = useRef(false);
    const onRead = useCallback((text: string) => {
        scanned.current = true;
        setValue(text);
        setCamera(false);
    }, []);
    useEffect(() => {
        if (scanned.current && !camera) {
            scanned.current = false;
            form.current?.requestSubmit();
        }
    }, [value, camera]);
    return (
        <section className={styles.scan}>
            <button
                type="button"
                className={styles.scanDock}
                disabled={disabled || pending}
                onClick={() => setCamera(true)}
            >
                Сканировать QR
            </button>
            {camera && (
                <CameraScanner
                    onRead={onRead}
                    onClose={() => setCamera(false)}
                />
            )}
            <h1>Скан мешка</h1>
            <p>Считайте QR сканером в поле или введите номер заказа.</p>
            <form
                ref={form}
                onSubmit={async (event) => {
                    event.preventDefault();
                    if (pending || disabled) return;
                    setError('');
                    const ref = parseBagReference(
                        value,
                        window.location.origin,
                    );
                    if (!ref) {
                        setError(
                            'Нужен номер заказа или QR-ссылка этого терминала.',
                        );
                        return;
                    }
                    setPending(true);
                    try {
                        const label =
                            ref.kind === 'label'
                                ? await requestJson<{
                                      project_id: number;
                                      unit_id: number | null;
                                  }>(`/production/labels/${ref.token}`, {
                                      cache: 'no-store',
                                  })
                                : null;
                        const id =
                            ref.kind === 'label'
                                ? label!.project_id
                                : ref.kind === 'project'
                                  ? ref.id
                                  : (
                                        await run((token) =>
                                            productionApi.resolveOrder(
                                                token,
                                                ref.id,
                                            ),
                                        )
                                    ).project_id;
                        // Validate existence and access before changing the selected bag.
                        await run((token) =>
                            productionApi.project(token, id, undefined, station),
                        );
                        onOpen(
                            id,
                            ref.kind === 'label'
                                ? (label?.unit_id ?? undefined)
                                : ref.unit,
                        );
                        setValue('');
                    } catch (e) {
                        setError(
                            e instanceof Error
                                ? e.message
                                : 'Не удалось открыть мешок',
                        );
                    } finally {
                        setPending(false);
                    }
                }}
            >
                <input
                    aria-label="QR мешка или номер заказа"
                    placeholder="QR мешка или номер заказа"
                    autoComplete="off"
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    maxLength={2048}
                    disabled={pending || disabled}
                />
                <button
                    className={styles.primary}
                    disabled={pending || disabled || !value.trim()}
                >
                    {pending ? 'Проверяем…' : 'Открыть'}
                </button>
            </form>
            {error && (
                <p role="alert" className={styles.error}>
                    {error}
                </p>
            )}
        </section>
    );
}
