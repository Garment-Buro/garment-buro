import type { AuthProfileData, AuthUser } from './types';
import { createAuthProfileData } from './utils/auth.ts';

type ProfileTransport = {
    save: (profile: AuthProfileData, signal: AbortSignal) => Promise<AuthUser>;
    remove: (signal: AbortSignal) => Promise<void>;
    confirm: (user: AuthUser) => void;
    logout: () => void | Promise<void>;
};
type ProfileState = {
    account: string | null;
    profile: AuthProfileData;
    status: 'idle' | 'saving' | 'saved' | 'deleting';
    error: unknown | null;
};

/** A form draft belongs to one identity session; the database confirms all writes. */
export class ProfileEditor {
    private snapshot: ProfileState = { account: null, profile: createAuthProfileData(null), status: 'idle', error: null };
    private listeners = new Set<() => void>();
    private controller: AbortController | null = null;
    private transport: ProfileTransport | null = null;
    private generation = 0;

    getSnapshot = () => this.snapshot;
    subscribe = (listener: () => void) => {
        this.listeners.add(listener);
        return () => { this.listeners.delete(listener); };
    };
    private publish(value: ProfileState) {
        this.snapshot = value;
        this.listeners.forEach(listener => listener());
    }
    setAccount = (account: string | null, user: AuthUser | null, transport: ProfileTransport | null) => {
        this.dispose();
        this.transport = transport;
        this.publish({ account, profile: createAuthProfileData(user), status: 'idle', error: null });
    };
    setField = <Field extends keyof AuthProfileData>(field: Field, value: AuthProfileData[Field]) => {
        if (this.controller) return;
        this.publish({ ...this.snapshot, profile: { ...this.snapshot.profile, [field]: value }, status: 'idle', error: null });
    };
    private async perform(deleting: boolean) {
        const transport = this.transport;
        if (!transport || this.controller) return false;
        const generation = this.generation;
        const controller = new AbortController();
        this.controller = controller;
        this.publish({ ...this.snapshot, status: deleting ? 'deleting' : 'saving', error: null });
        try {
            const user = deleting
                ? await transport.remove(controller.signal)
                : await transport.save(this.snapshot.profile, controller.signal);
            if (controller.signal.aborted || generation !== this.generation) return false;
            if (deleting) await transport.logout();
            else if (user) transport.confirm(user);
            if (controller.signal.aborted || generation !== this.generation) return true;
            this.publish({ ...this.snapshot, status: deleting ? 'idle' : 'saved', error: null });
            return true;
        } catch (error) {
            if (controller.signal.aborted || generation !== this.generation) return false;
            this.publish({ ...this.snapshot, status: 'idle', error });
            return false;
        } finally {
            if (this.controller === controller) this.controller = null;
        }
    }
    save = () => this.perform(false);
    remove = () => this.perform(true);
    dispose = () => {
        this.generation++;
        this.controller?.abort();
        this.controller = null;
        this.transport = null;
    };
}
