'use client';

import { useEffect, useRef, useState } from 'react';
import { isCustomerSessionCurrent, runForCustomer, useCustomerAccount } from '@/hooks/catalog/customerSession';
import { createProject, getProjectByClientKey, uploadProjectImage } from '@/lib/api/projects';
import { getConstructorProduct } from '@/lib/api/storefront';
import {
    importLegacyProject, removeImportedLegacyProject, scanLegacyProjects,
    type LegacyMigrationTransport, type LegacyProjectEntry, type LegacyProjectScan,
} from '@/lib/projects/legacyMigration';
import type { ProjectSummary } from '@/lib/projects/types';

type RowResult = { receipt?: ProjectSummary; error?: unknown };
const readSources = (): LegacyProjectScan => {
    if (typeof window === 'undefined') return { entries: [], issues: [] };
    try { return scanLegacyProjects(window.localStorage); }
    catch { return { entries: [], issues: [{ key: 'storage-unavailable', title: 'Локальные проекты', reason: 'Браузер запретил доступ к локальному хранилищу. Данные не изменены.' }] }; }
};

/** Explicit migration only. All results and selection belong to this account session. */
export function useLegacyProjectMigration() {
    const account = useCustomerAccount();
    const [scan, setScan] = useState(readSources);
    const [selected, setSelected] = useState<Set<string>>(() => new Set());
    const [results, setResults] = useState<Record<string, RowResult>>({});
    const [busy, setBusy] = useState(false);
    const [notice, setNotice] = useState('');
    const controller = useRef<AbortController | null>(null);
    useEffect(() => () => { controller.current?.abort(); controller.current = null; }, [account.key]);

    const refresh = () => {
        if (controller.current) return;
        setScan(readSources()); setSelected(new Set()); setResults({}); setNotice('');
    };
    const perform = async (operation: (options: {
        storage: Storage; transport: LegacyMigrationTransport; origin: string;
        signal: AbortSignal; assertCurrent: () => void;
    }) => Promise<void>) => {
        const userId = account.userId;
        if (userId === null || controller.current) return;
        const current = new AbortController(); controller.current = current;
        const assertCurrent = () => {
            current.signal.throwIfAborted();
            if (!isCustomerSessionCurrent(userId, account.key)) throw new DOMException('Account changed', 'AbortError');
        };
        const run = <Result,>(operation: (token: string) => Promise<Result>) => runForCustomer(userId, operation, account.key);
        setBusy(true); setNotice('');
        try {
            await operation({
                storage: window.localStorage, origin: window.location.origin, signal: current.signal, assertCurrent,
                transport: {
                    receipt: (key, signal) => run(token => getProjectByClientKey(key, token, signal)),
                    product: getConstructorProduct,
                    upload: (image, signal) => run(token => uploadProjectImage(image, token, signal)),
                    create: (payload, signal) => run(token => createProject(payload, token, signal)),
                },
            });
        } finally {
            if (controller.current === current) {
                controller.current = null;
                if (isCustomerSessionCurrent(userId, account.key)) setBusy(false);
            }
        }
    };
    const importSelected = () => perform(async options => {
        for (const entry of scan.entries.filter(entry => selected.has(entry.key))) {
            options.assertCurrent();
            try {
                const receipt = await importLegacyProject(entry, options);
                options.assertCurrent();
                setResults(previous => ({ ...previous, [entry.key]: { receipt } }));
            } catch (error) {
                options.assertCurrent();
                setResults(previous => ({ ...previous, [entry.key]: { error } }));
            }
        }
    }).catch(() => { /* A changed account or an unmount cancels publication. */ });
    const removeLocalCopy = (entry: LegacyProjectEntry) => perform(async options => {
        const receipt = results[entry.key]?.receipt;
        if (!receipt) return;
        try {
            if (!navigator.locks) throw new Error('Этот браузер не поддерживает безопасное удаление локальных копий. Копия сохранена.');
            const removed = await navigator.locks.request('garment-legacy-project-storage', { mode: 'exclusive', signal: options.signal },
                () => removeImportedLegacyProject(entry, receipt.id, options));
            options.assertCurrent();
            if (!removed) throw new Error('Локальная запись изменилась. Обновите список; новая версия сохранена в браузере.');
            setScan(readSources()); setSelected(new Set()); setResults({});
            setNotice('Локальная копия убрана. Проект сохранён в аккаунте.');
        } catch (error) {
            options.assertCurrent();
            setResults(previous => ({ ...previous, [entry.key]: { receipt, error } }));
        }
    }).catch(() => { /* Keep the browser source on cancellation. */ });

    return {
        ...scan, selected, results, busy, notice, refresh, importSelected, removeLocalCopy,
        toggle: (key: string) => {
            if (controller.current) return;
            setSelected(previous => { const next = new Set(previous); if (next.has(key)) next.delete(key); else next.add(key); return next; });
        },
    };
}
