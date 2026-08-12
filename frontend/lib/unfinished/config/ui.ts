import type { ProfilePanelTab, ProfileTab } from '@/lib/unfinished/types';

export const TAB_FADE_OUT_MS = 220;
export const UNFINISHED_SHEET_EXIT_MS = 420;
export const COLLAPSED_PANEL_SWIPE_UP_THRESHOLD_PX = 36;
export const PANEL_STEP_SWIPE_THRESHOLD_PX = 36;
export const PANEL_TOGGLE_CLICK_SUPPRESSION_MS = 450;
export const ENABLE_UNFINISHED_PANEL_BACKGROUND_SWITCH = false;
export const COLLECTION_HERO_IMAGE = '/my_collection_template.webp';
export const DRAFTS_PANEL_BACKGROUND = "url('/unfinished_bg.webp')";

export const SECTION_BACKGROUND_IMAGES = [
    '/landing_1.webp',
    '/unfinished_content_bg.webp',
    '/unfinished_bg_2.webp',
    '/unfinished_bg_3.webp',
    '/my_collection_bg.webp',
    '/profile_bg.webp',
];

export const navigationItems: Array<{ id: ProfileTab; label: string }> = [
    { id: 'my-collection', label: 'MY COLLECTION' },
    { id: 'profile', label: 'PROFILE' },
    { id: 'unfinished', label: 'UNFINISHED' },
];

export const profileTabs: Array<{ id: ProfilePanelTab; label: string; icon?: string }> = [
    { id: 'discounts', label: 'Скидки', icon: '/discount_header_icon.svg' },
    { id: 'orders', label: 'ЗАКАЗЫ' },
    { id: 'support', label: 'ПОДДЕРЖКА' },
    { id: 'settings', label: 'НАСТРОЙКИ' },
];

export const tabTitles: Record<ProfileTab, string> = {
    'my-collection': 'MY COLLECTION',
    profile: 'PROFILE',
    unfinished: 'UNFINISHED',
};

export const tabChromeColors: Record<ProfileTab, string> = {
    'my-collection': '#DFE4E4',
    profile: '#EDEDEB',
    unfinished: '#D3D5D7',
};

export const emptyStateCopy: Record<ProfileTab, { title: string; text: string; cta?: string }> = {
    'my-collection': { title: 'Здесь пока нет вещей.', text: 'Купленные изделия появятся в вашей коллекции.' },
    profile: { title: 'Профиль скоро появится.', text: 'Здесь будут ваши данные и настройки.' },
    unfinished: { title: 'Здесь пока нет вещей.', text: 'Создайте первый дизайн или сохраните черновик.', cta: 'Создать\u00A0\u00A0>' },
};
