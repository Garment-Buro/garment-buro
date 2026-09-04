'use client';

import { useEffect } from 'react';

import {
    clearInstallPrompt,
    retainInstallPrompt,
    type BeforeInstallPromptEvent,
} from '@/lib/pwa/installPrompt';

export const PwaRegistration = () => {
    useEffect(() => {
        const onBeforeInstallPrompt = (event: Event) => {
            event.preventDefault();
            retainInstallPrompt(event as BeforeInstallPromptEvent);
        };
        const onInstalled = () => clearInstallPrompt();

        window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt);
        window.addEventListener('appinstalled', onInstalled);

        if (!('serviceWorker' in navigator)) {
            return () => {
                window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt);
                window.removeEventListener('appinstalled', onInstalled);
            };
        }

        if (process.env.NODE_ENV !== 'production') {
            void navigator.serviceWorker.getRegistrations().then(registrations => {
                registrations.forEach(registration => void registration.unregister());
            });
            return () => {
                window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt);
                window.removeEventListener('appinstalled', onInstalled);
            };
        }

        const register = () => {
            void navigator.serviceWorker.register('/sw.js', {
                scope: '/',
                updateViaCache: 'none',
            });
        };

        if (document.readyState === 'complete') {
            register();
        } else {
            window.addEventListener('load', register, { once: true });
        }

        return () => {
            window.removeEventListener('load', register);
            window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt);
            window.removeEventListener('appinstalled', onInstalled);
        };
    }, []);

    return null;
};
