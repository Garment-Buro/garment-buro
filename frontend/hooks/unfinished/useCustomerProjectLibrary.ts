'use client';

import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { runForCustomer, useCustomerAccount, isCustomerSessionCurrent } from '@/hooks/catalog/customerSession';
import { useCustomerProject } from '@/hooks/projects/useCustomerProject';
import { deleteProject, getProjects } from '@/lib/api/projects';
import { PagedResource } from '@/lib/catalog/pagedResource';
import type { ProjectKind, ProjectSummary } from '@/lib/projects/types';

/** Metadata pages only; the selected project alone loads its canvas and images. */
export function useCustomerProjectLibrary(kind: ProjectKind | null) {
    const account = useCustomerAccount();
    const key = `${account.key ?? 'guest'}:${kind ?? 'inactive'}`;
    const [resource] = useState(() => new PagedResource<ProjectSummary, number>());
    const snapshot = useSyncExternalStore(resource.subscribe, resource.getSnapshot, resource.getSnapshot);
    const [selection, setSelection] = useState<{ key: string; id: number } | null>(null);
    const [deletion, setDeletion] = useState<{ key: string; busy: boolean; error: unknown } | null>(null);
    const deleteController = useRef<AbortController | null>(null);

    useEffect(() => {
        const userId = account.userId;
        if (userId === null || kind === null) { resource.dispose(); return; }
        void resource.start(key, (cursor, signal) => runForCustomer(userId,
            token => getProjects(kind, token, { limit: 24, cursor }, signal), account.key));
        return resource.dispose;
    }, [account.key, account.userId, key, kind, resource]);

    useEffect(() => () => {
        deleteController.current?.abort();
        deleteController.current = null;
    }, [key]);

    const state = snapshot.key === key && account.userId !== null && kind !== null ? snapshot : {
        key, status: 'loading' as const, items: [], nextCursor: null, loadingMore: false, error: null,
    };
    const selected = state.items.find(item => selection?.key === key && item.id === selection.id) ?? state.items[0];
    const preview = useCustomerProject(selected ? String(selected.id) : null);
    const restored = preview.document?.id === selected?.id ? preview.restored : null;
    const previewVersion = preview.document?.version;
    useEffect(() => {
        if (selected && preview.document?.id === selected.id && previewVersion !== undefined && selected.version > previewVersion) {
            void preview.editor.reload();
        }
    }, [selected, preview.document?.id, previewVersion, preview.editor]);

    const removeSelected = async () => {
        const userId = account.userId;
        if (!selected || userId === null || deleteController.current) return false;
        const controller = new AbortController();
        deleteController.current = controller;
        setDeletion({ key, busy: true, error: null });
        try {
            await runForCustomer(userId, token => deleteProject(selected.id, selected.version, token, controller.signal), account.key);
            controller.signal.throwIfAborted();
            await resource.reload();
            controller.signal.throwIfAborted();
            return true;
        } catch (error) {
            if (!controller.signal.aborted && isCustomerSessionCurrent(userId, account.key)) {
                setDeletion({ key, busy: false, error });
            }
            return false;
        } finally {
            if (deleteController.current === controller) {
                deleteController.current = null;
                setDeletion(previous => previous?.key === key ? { ...previous, busy: false } : previous);
            }
        }
    };

    return {
        ...state, account, selected, restored,
        previewLoading: Boolean(selected) && (!restored || preview.status === 'loading') && !preview.error,
        previewError: preview.error,
        retryPreview: preview.reload,
        select: (id: number) => setSelection({ key, id }),
        loadMore: resource.loadMore,
        retry: resource.reload,
        removeSelected,
        clearDeleteError: () => setDeletion(previous => previous?.busy ? previous : null),
        deleting: deletion?.key === key && deletion.busy,
        deleteError: deletion?.key === key ? deletion.error : null,
    };
}
