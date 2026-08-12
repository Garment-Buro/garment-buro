"use client";

import NextLink from 'next/link';
import { useCookieConsent } from '@/hooks/browser/useCookieConsent';
import styles from './CookieConsent.module.css';

export const CookieConsent = () => {
    const { isMounted, isVisible, accept } = useCookieConsent();

    if (!isMounted) return null;

    return (
        <aside
            className={`${styles.banner} ${isVisible ? styles.bannerVisible : styles.bannerHidden}`}
            aria-label="Использование файлов cookie"
        >
            <div className={styles.copy}>
                Мы используем файлы cookie. Продолжая использовать сайт, вы соглашаетесь с{' '}
                <NextLink href="/policy" className={styles.link}>
                    Политикой конфиденциальности
                </NextLink>{' '}
                и{' '}
                <NextLink href="/consent" className={styles.link}>
                    согласием на обработку персональных данных
                </NextLink>.
            </div>

            <button
                type="button"
                onClick={accept}
                className={styles.acceptButton}
            >
                Принять
            </button>
        </aside>
    );
};
