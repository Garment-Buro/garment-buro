import type { AuthSessionResponse } from '@/lib/auth/types';

export class AuthSessionCoordinator {
    private refreshPromises = new Map<string, Promise<AuthSessionResponse>>();
    private logoutPromises = new Map<string, Promise<void>>();
    private readonly refreshOperation: () => Promise<AuthSessionResponse>;
    private readonly logoutOperation: () => Promise<void>;

    constructor(
        refreshOperation: () => Promise<AuthSessionResponse>,
        logoutOperation: () => Promise<void>,
    ) {
        this.refreshOperation = refreshOperation;
        this.logoutOperation = logoutOperation;
    }

    refresh(scope = 'default'): Promise<AuthSessionResponse> {
        let promise = this.refreshPromises.get(scope);
        if (!promise) {
            promise = this.refreshOperation().finally(() => {
                this.refreshPromises.delete(scope);
            });
            this.refreshPromises.set(scope, promise);
        }
        return promise;
    }

    logout(scope = 'default'): Promise<void> {
        let promise = this.logoutPromises.get(scope);
        if (!promise) {
            promise = this.logoutOperation().finally(() => {
                this.logoutPromises.delete(scope);
            });
            this.logoutPromises.set(scope, promise);
        }
        return promise;
    }
}
