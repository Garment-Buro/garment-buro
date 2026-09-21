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

const signedOut = (error = '') => ({
    user: null,
    isSessionReady: true,
    isAuthenticated: false,
    error,
});

const isUnauthorized = (error: unknown) =>
    error instanceof ApiError && error.status === 401;

export const useProductionAuthStore = create<ProductionAuth>((set) => ({
    user: null, isSessionReady: false, isAuthenticated: false, error: '',
    initialize: async () => {
        try {
            const user = await requestJson<Employee>('/production/me', { cache: 'no-store' });
            set({ user, isAuthenticated: true, isSessionReady: true, error: '' });
        } catch (error) {
            set(
                signedOut(
                    isUnauthorized(error)
                        ? ''
                        : 'Не удалось проверить сессию. Проверьте подключение.',
                ),
            );
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
        let error = '';
        try {
            await requestJson('/production/auth/logout', { method: 'POST' });
        } catch (failure) {
            if (!isUnauthorized(failure)) {
                error =
                    'Сеанс закрыт на этом устройстве. Сервер не подтвердил выход из-за соединения.';
            }
        }
        set(signedOut(error));
    },
    runAuthenticated: async (operation) => {
        try { return await operation(''); }
        catch (error) {
            if (isUnauthorized(error)) {
                set(signedOut());
                throw new ApiError('Сессия завершена. Войдите снова.', 401);
            }
            throw error;
        }
    },
}));
