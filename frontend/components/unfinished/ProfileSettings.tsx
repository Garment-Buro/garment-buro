'use client';

import Link from 'next/link';
import { useAuthSettings } from '@/hooks/auth/useAuthSettings';
import type { AuthUser } from '@/lib/auth/types';
import { useAuthStore } from '@/store/authStore';
import styles from './UnfinishedSurface.module.css';

export function ProfileSettings({ user, onMigrateProjects }: { user: AuthUser; onMigrateProjects: () => void }) {
    const updateUser = useAuthStore(state => state.updateUser);
    const logout = useAuthStore(state => state.logout);
    const settings = useAuthSettings({ user, updateUser, logout });
    const busy = settings.saving || settings.deleting;
    return (
        <form className={styles.profileSettingsCard} onSubmit={event => { event.preventDefault(); void settings.saveProfile(); }}>
            <Link className={styles.profileAccountAction} href="/profile/public" prefetch={false}>Мой публичный профиль</Link>
            <span className={styles.profileSectionLabel}>ЛИЧНАЯ ИНФОРМАЦИЯ</span>
            <label className={styles.profileField}>
                <span>Имя профиля</span>
                <input value={settings.profile.first_name} autoComplete="given-name" maxLength={255} disabled={busy}
                    onChange={event => settings.setProfileField('first_name', event.target.value)} />
            </label>
            <label className={styles.profileField}>
                <span>Пол</span>
                <select className={styles.profileSelect} value={settings.profile.gender} disabled={busy}
                    onChange={event => settings.setProfileField('gender', event.target.value)}>
                    <option value="">Не выбран</option>
                    <option value="male">Мужской</option>
                    <option value="female">Женский</option>
                </select>
            </label>
            <span className={styles.profileSectionLabel}>КОНТАКТЫ</span>
            <label className={styles.profileField}>
                <span>Телефон</span>
                <input type="tel" value={settings.profile.phone} autoComplete="tel" maxLength={64} disabled={busy}
                    onChange={event => settings.setProfileField('phone', event.target.value)} />
            </label>
            <label className={styles.profileField}>
                <span>Почта</span>
                <input type="email" value={user.email ?? ''} readOnly autoComplete="email" />
            </label>
            {Boolean(settings.error) && <p role="alert" className={styles.profileMessage}>
                Не удалось выполнить действие. Проверьте соединение и повторите попытку.
            </p>}
            {settings.saved && <p role="status" className={styles.profileMessage}>Изменения сохранены.</p>}
            <button className={styles.profilePrimaryButton} type="submit" disabled={busy}>
                {settings.saving ? 'СОХРАНЯЕМ…' : 'СОХРАНИТЬ'}
            </button>
            <button className={styles.profileAccountAction} type="button" disabled={busy} onClick={() => void logout()}>
                Выйти из профиля
            </button>
            <button className={styles.profileAccountAction} type="button" disabled={busy} onClick={onMigrateProjects}>
                Перенести старые проекты из браузера
            </button>
            <button className={styles.profileDeleteAccount} type="button" disabled={busy} onClick={() => void settings.removeProfile()}>
                {settings.deleting ? 'Удаляем…' : 'Удалить аккаунт'}
            </button>
        </form>
    );
}
