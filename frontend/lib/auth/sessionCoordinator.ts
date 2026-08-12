import type { AuthSessionResponse } from '@/lib/auth/types';

export class AuthSessionCoordinator {
    private refreshPromise: Promise<AuthSessionResponse> | null = null;
    private logoutPromise: Promise<void> | null = null;
    private readonly refreshOperation: () => Promise<AuthSessionResponse>;
    private readonly logoutOperation: () => Promise<void>;

    constructor(
        refreshOperation: () => Promise<AuthSessionResponse>,
        logoutOperation: () => Promise<void>,
    ) {
        this.refreshOperation = refreshOperation;
        this.logoutOperation = logoutOperation;
    }

    refresh(): Promise<AuthSessionResponse> {
        if (!this.refreshPromise) {
            this.refreshPromise = this.refreshOperation().finally(() => {
                this.refreshPromise = null;
            });
        }
        return this.refreshPromise;
    }

    logout(): Promise<void> {
        if (!this.logoutPromise) {
            this.logoutPromise = this.logoutOperation().finally(() => {
                this.logoutPromise = null;
            });
        }
        return this.logoutPromise;
    }
}
