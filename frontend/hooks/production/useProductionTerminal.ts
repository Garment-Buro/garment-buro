'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { productionApi } from '@/lib/api/production';
import { useAuthStore } from '@/store/authStore';
import type { Command, Employee, Project, Queue } from '@/lib/production/types';

export function useProductionTerminal() {
    const run = useAuthStore((state) => state.runAuthenticated);
    const userId = useAuthStore((state) => state.user?.id);
    const [employee, setEmployee] = useState<Employee | null>(null);
    const [queue, setQueue] = useState<Queue>({ items: [], next_cursor: null });
    const [project, setProject] = useState<Project | null>(null);
    const [selected, setSelected] = useState<number | null>(null);
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [refresh, setRefresh] = useState(0);
    const locked = useRef(false);
    const reload = useCallback(() => setRefresh((value) => value + 1), []);

    useEffect(() => {
        const id = Number(
            new URLSearchParams(window.location.search).get('project'),
        );
        if (Number.isSafeInteger(id) && id > 0) setSelected(id);
    }, []);
    useEffect(() => {
        const controller = new AbortController();
        setLoading(true);
        setError('');
        setProject(null);
        void (async () => {
            try {
                const me = await run((token) =>
                    productionApi.me(token, controller.signal),
                );
                const list = await run((token) =>
                    productionApi.queue(token, undefined, controller.signal),
                );
                const detail = selected
                    ? await run((token) =>
                          productionApi.project(
                              token,
                              selected,
                              controller.signal,
                          ),
                      )
                    : null;
                if (controller.signal.aborted) return;
                setEmployee(me);
                setQueue(list);
                setProject(detail);
            } catch (error) {
                if (!controller.signal.aborted) {
                    setEmployee(null);
                    setQueue({ items: [], next_cursor: null });
                    setError(
                        error instanceof Error
                            ? error.message
                            : 'Не удалось загрузить терминал',
                    );
                }
            } finally {
                if (!controller.signal.aborted) setLoading(false);
            }
        })();
        return () => controller.abort();
    }, [run, userId, selected, refresh]);

    const select = (id: number) => {
        if (locked.current) return;
        setSelected(id);
        setNotice('');
        window.history.replaceState(null, '', `/production?project=${id}`);
    };
    const send = async (command: Command) => {
        if (!project || locked.current) return false;
        locked.current = true;
        setBusy(true);
        setError('');
        setNotice('');
        // One key survives the auth-refresh retry. Never queue physical actions offline.
        const key = crypto.randomUUID();
        try {
            await run((token) =>
                productionApi.command(
                    token,
                    project.project_id,
                    project.version,
                    key,
                    command,
                ),
            );
            setNotice('Действие сохранено в журнале');
            reload();
            return true;
        } catch (error) {
            setError(
                `${error instanceof Error ? error.message : 'Нет связи с сервером'}. Обновите заказ и проверьте журнал перед повтором.`,
            );
            return false;
        } finally {
            locked.current = false;
            setBusy(false);
        }
    };
    const more = async () => {
        if (!queue.next_cursor || locked.current) return;
        locked.current = true;
        setBusy(true);
        try {
            const page = await run((token) =>
                productionApi.queue(token, queue.next_cursor!),
            );
            setQueue((old) => ({
                items: [
                    ...old.items,
                    ...page.items.filter(
                        (x) =>
                            !old.items.some(
                                (y) => y.project_id === x.project_id,
                            ),
                    ),
                ],
                next_cursor: page.next_cursor,
            }));
        } catch (error) {
            setError(
                error instanceof Error
                    ? error.message
                    : 'Не удалось загрузить список',
            );
        } finally {
            locked.current = false;
            setBusy(false);
        }
    };
    return {
        employee,
        queue,
        project,
        selected,
        loading,
        busy,
        error,
        notice,
        reload,
        select,
        send,
        more,
    };
}
