'use client';

import { create } from 'zustand';
import { ApiError, requestJson } from '@/lib/api/http';
import type { Employee } from '@/lib/production/types';

type ProductionAuth = {
    user: Employee | null;
    isSessionReady: boolean;
    isAuthenticated: boolean;
    error: string;
    initialize: () => Promise<void>;
    login: (code: string) => Promise<void>;
    logout: () => Promise<void>;
    runAuthenticated: <T>(operation: (token: string) => Promise<T>) => Promise<T>;
};

export const useProductionAuthStore = create<ProductionAuth>((set) => ({
    user: null, isSessionReady: false, isAuthenticated: false, error: '',
    initialize: async () => {
        try {
            const user = await requestJson<Employee>('/production/me', { cache: 'no-store' });
            set({ user, isAuthenticated: true, isSessionReady: true, error: '' });
        } catch (error) {
            set({ user: null, isAuthenticated: false, isSessionReady: true,
                error: error instanceof ApiError && error.status === 401 ? '' : 'Не удалось проверить сессию. Проверьте подключение.' });
        }
    },
    login: async (code) => {
        await requestJson('/production/auth/login', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code }),
        });
        const user = await requestJson<Employee>('/production/me', { cache: 'no-store' });
        set({ user, isAuthenticated: true, isSessionReady: true, error: '' });
    },
    logout: async () => {
        try {
            await requestJson('/production/auth/logout', { method: 'POST' });
            set({ user: null, isAuthenticated: false, error: '' });
        } catch {
            set({ error: 'Не удалось завершить сессию. Повторите выход после восстановления связи.' });
        }
    },
    runAuthenticated: async (operation) => {
        try { return await operation(''); }
        catch (error) {
            if (error instanceof ApiError && error.status === 401) {
                set({ user: null, isAuthenticated: false });
            }
            throw error;
        }
    },
}));
