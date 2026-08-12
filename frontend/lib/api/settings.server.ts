import type { LandingSettings } from '@/lib/settings/types';

import { serverRequestJson } from '@/lib/server/backend/http';

export const getServerLandingSettings = () => serverRequestJson<LandingSettings>('/settings', {
    next: { revalidate: 60 },
});
