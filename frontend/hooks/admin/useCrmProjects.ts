'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { getCrmProjects } from '@/lib/api/crm';
import type { CrmProjectSummary } from '@/lib/crm/types';
import { useAuthStore } from '@/store/authStore';

type CrmProjectsState = {
    projects: CrmProjectSummary[];
    nextCursor: number | null;
    isLoading: boolean;
    isLoadingMore: boolean;
    hasError: boolean;
};

const INITIAL_STATE: CrmProjectsState = {
    projects: [],
    nextCursor: null,
    isLoading: true,
    isLoadingMore: false,
    hasError: false,
};

export const useCrmProjects = (enabled: boolean) => {
    const runAuthenticated = useAuthStore(state => state.runAuthenticated);
    const [state, setState] = useState<CrmProjectsState>(INITIAL_STATE);
    const activeController = useRef<AbortController | null>(null);

    const requestFirstPage = useCallback(() => {
        if (!enabled) return;
        activeController.current?.abort();
        const controller = new AbortController();
        activeController.current = controller;
        void runAuthenticated(token => getCrmProjects(token, {}, controller.signal))
            .then((page) => {
                if (controller.signal.aborted) return;
                setState({
                    projects: page.items,
                    nextCursor: page.next_cursor,
                    isLoading: false,
                    isLoadingMore: false,
                    hasError: false,
                });
            })
            .catch(() => {
                if (controller.signal.aborted) return;
                setState({ ...INITIAL_STATE, isLoading: false, hasError: true });
            });
    }, [enabled, runAuthenticated]);

    useEffect(() => {
        if (enabled) requestFirstPage();
        return () => activeController.current?.abort();
    }, [enabled, requestFirstPage]);

    const retry = useCallback(() => {
        setState(INITIAL_STATE);
        requestFirstPage();
    }, [requestFirstPage]);

    const loadMore = useCallback(() => {
        if (!enabled || state.nextCursor === null || state.isLoadingMore) return;
        activeController.current?.abort();
        const controller = new AbortController();
        activeController.current = controller;
        const cursor = state.nextCursor;
        setState(current => ({ ...current, isLoadingMore: true, hasError: false }));
        void runAuthenticated(token => getCrmProjects(token, { cursor }, controller.signal))
            .then((page) => {
                if (controller.signal.aborted) return;
                setState(current => ({
                    projects: [...current.projects, ...page.items],
                    nextCursor: page.next_cursor,
                    isLoading: false,
                    isLoadingMore: false,
                    hasError: false,
                }));
            })
            .catch(() => {
                if (controller.signal.aborted) return;
                setState(current => ({ ...current, isLoadingMore: false, hasError: true }));
            });
    }, [enabled, runAuthenticated, state.isLoadingMore, state.nextCursor]);

    return {
        ...state,
        retry,
        loadMore,
    };
};
