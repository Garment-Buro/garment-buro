'use client';

import { useEffect, useState, useSyncExternalStore } from 'react';
import { runForCustomer, useCustomerAccount } from '@/hooks/catalog/customerSession';
import { createProject, getProject, getProjectImages, updateProject, uploadProjectImage } from '@/lib/api/projects';
import { ProjectEditor, type ProjectTransport } from '@/lib/projects/editor';

export function useCustomerProject(projectId: string | null) {
    const account = useCustomerAccount();
    const [editor] = useState(() => new ProjectEditor({ origin: typeof window === 'undefined' ? '' : window.location.origin }));
    const state = useSyncExternalStore(editor.subscribe, editor.getSnapshot, editor.getSnapshot);
    const id = projectId && /^[1-9]\d*$/.test(projectId) ? Number(projectId) : null;
    const validId = id !== null && Number.isSafeInteger(id) && id <= 2_147_483_647 ? id : null;

    useEffect(() => {
        const userId = account.userId;
        const transport: ProjectTransport | null = userId === null ? null : {
            create: (payload, signal) => runForCustomer(userId, token => createProject(payload, token, signal), account.key),
            update: (id, payload, signal) => runForCustomer(userId, token => updateProject(id, payload, token, signal), account.key),
            get: (id, signal) => runForCustomer(userId, token => getProject(id, token, signal), account.key),
            images: (id, version, signal) => runForCustomer(userId, token => getProjectImages(id, version, token, signal), account.key),
            upload: (image, signal) => runForCustomer(userId, token => uploadProjectImage(image, token, signal), account.key),
        };
        editor.setAccount(account.key, transport);
        if (userId !== null && validId !== null) void editor.load(validId);
        return editor.dispose;
    }, [account.key, account.userId, editor, validId]);

    const current = state.account === account.key;
    return {
        editor,
        account,
        document: current ? state.document : null,
        restored: current ? state.restored : null,
        status: current ? state.status : 'idle',
        error: current ? state.error : null,
        invalidId: Boolean(projectId) && validId === null,
        isExisting: Boolean(projectId),
        reload: () => validId === null ? editor.reload() : editor.load(validId),
    };
}
