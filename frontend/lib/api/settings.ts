import type { LandingSettings } from '@/lib/settings/types';

import { request, requestJson } from './http';
import { bearerHeaders } from './headers';

export const getLandingSettings = (signal?: AbortSignal) => requestJson<LandingSettings>('/settings', {
    signal,
});

export const updateLandingSettings = async (settings: LandingSettings, token?: string) => {
    await request('/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...bearerHeaders(token) },
        body: JSON.stringify(settings),
    });
};
