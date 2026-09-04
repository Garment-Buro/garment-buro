'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useCallback, useEffect, useState, type ReactNode } from 'react';

import {
    clearInstallPrompt,
    getInstallPrompt,
    subscribeToInstallPrompt,
    type BeforeInstallPromptEvent,
} from '@/lib/pwa/installPrompt';

import styles from './PwaInstallGate.module.css';

const PENDING_CONSTRUCTOR_KEY = 'gb_pwa_pending_constructor';

type GateMode = 'checking' | 'browser' | 'installed' | 'standalone';

type NavigatorWithStandalone = Navigator & {
    standalone?: boolean;
};

const isStandalone = () => (
    window.matchMedia('(display-mode: standalone)').matches
    || (navigator as NavigatorWithStandalone).standalone === true
);

const isSafeConstructorPath = (value: string | null): value is string => {
    if (!value) return false;
    return (value === '/constructor' || value.startsWith('/constructor?'))
        && !value.includes('\\');
};

export const PwaInstallGate = ({
    children,
    returnHref,
}: {
    children: ReactNode;
    returnHref: string;
}) => {
    const [mode, setMode] = useState<GateMode>('checking');
    const [installPrompt, setInstallPrompt] = useState<BeforeInstallPromptEvent | null>(null);
    const [ios, setIos] = useState(false);

    useEffect(() => {
        let mounted = true;
        const updateState = (callback: () => void) => {
            queueMicrotask(() => {
                if (mounted) callback();
            });
        };
        const currentPath = `${window.location.pathname}${window.location.search}`;

        if (isStandalone()) {
            const launchedFromManifest = new URLSearchParams(window.location.search).get('source') === 'pwa';
            const pendingPath = window.localStorage.getItem(PENDING_CONSTRUCTOR_KEY);
            if (launchedFromManifest && isSafeConstructorPath(pendingPath) && pendingPath !== currentPath) {
                window.localStorage.removeItem(PENDING_CONSTRUCTOR_KEY);
                window.location.replace(pendingPath);
                return;
            }

            window.localStorage.removeItem(PENDING_CONSTRUCTOR_KEY);
            updateState(() => setMode('standalone'));
            return () => {
                mounted = false;
            };
        }

        if (isSafeConstructorPath(currentPath)) {
            window.localStorage.setItem(PENDING_CONSTRUCTOR_KEY, currentPath);
        }
        updateState(() => {
            setIos(/iphone|ipad|ipod/i.test(navigator.userAgent));
            setInstallPrompt(getInstallPrompt());
            setMode('browser');
        });

        const onInstalled = () => {
            setInstallPrompt(null);
            setMode('installed');
        };
        const unsubscribe = subscribeToInstallPrompt(setInstallPrompt);

        window.addEventListener('appinstalled', onInstalled);
        return () => {
            mounted = false;
            unsubscribe();
            window.removeEventListener('appinstalled', onInstalled);
        };
    }, []);

    const requestInstall = useCallback(async () => {
        if (!installPrompt) return;
        await installPrompt.prompt();
        const choice = await installPrompt.userChoice;
        clearInstallPrompt();
        if (choice.outcome === 'accepted') setMode('installed');
    }, [installPrompt]);

    if (mode === 'standalone') return children;

    const title = mode === 'checking'
        ? 'Проверяем запуск'
        : mode === 'installed'
            ? 'Приложение установлено'
            : 'Конструктор работает в приложении';

    return (
        <main className={styles.screen} aria-live="polite">
            <section className={styles.card} aria-labelledby="pwa-gate-title">
                <Image
                    src="/pwa-icon-192.png"
                    alt=""
                    width={72}
                    height={72}
                    className={styles.logo}
                    priority
                />
                <p className={styles.eyebrow}>Garment Buro</p>
                <h1 id="pwa-gate-title">{title}</h1>

                {mode === 'checking' ? (
                    <p className={styles.copy}>Секунду — определяем, открыто ли приложение.</p>
                ) : mode === 'installed' ? (
                    <p className={styles.copy}>
                        Откройте Garment Buro с домашнего экрана. Выбранная модель уже сохранена.
                    </p>
                ) : (
                    <>
                        <p className={styles.copy}>
                            Лендинг можно смотреть в браузере. Для примерки и настройки модели установите PWA — выбранная модель откроется автоматически.
                        </p>
                        {ios ? (
                            <ol className={styles.steps}>
                                <li>Нажмите «Поделиться» в Safari.</li>
                                <li>Выберите «На экран Домой».</li>
                                <li>Откройте Garment Buro с домашнего экрана.</li>
                            </ol>
                        ) : installPrompt ? (
                            <button type="button" className={styles.installButton} onClick={requestInstall}>
                                Установить приложение
                            </button>
                        ) : (
                            <ol className={styles.steps}>
                                <li>Откройте меню браузера.</li>
                                <li>Выберите «Установить приложение» или «Добавить на главный экран».</li>
                                <li>Запустите Garment Buro по новой иконке.</li>
                            </ol>
                        )}
                    </>
                )}

                {mode !== 'checking' && (
                    <Link href={returnHref} className={styles.returnLink}>
                        Вернуться к коллекции
                    </Link>
                )}
            </section>
        </main>
    );
};
