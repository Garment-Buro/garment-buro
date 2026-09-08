'use client';

import { useRef, useState } from 'react';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import styles from './ProductionTerminal.module.css';

export function ProductionLogin() {
    const login = useProductionAuthStore((state) => state.login);
    const sessionError = useProductionAuthStore((state) => state.error);
    const [code, setCode] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const locked = useRef(false);
    return (
        <main className={styles.login}>
            <section className={styles.panel}>
                <p className={styles.eyebrow}>GARMENT BURO · ПРОИЗВОДСТВО</p>
                <h1>Вход на участок</h1>
                <p>Введите личный код из 6 цифр. Код и доступ к участку выдаёт руководитель производства.</p>
                <form onSubmit={async (event) => {
                    event.preventDefault();
                    if (locked.current || !/^[0-9]{6}$/.test(code)) return;
                    locked.current = true; setLoading(true); setError('');
                    try { await login(code); }
                    catch (failure) {
                        setError(failure instanceof Error ? failure.message : 'Не удалось войти');
                        setCode('');
                    } finally { locked.current = false; setLoading(false); }
                }}>
                    <label htmlFor="production-code">Личный код сотрудника</label>
                    <input id="production-code" type="password" inputMode="numeric"
                        autoComplete="current-password" required pattern="[0-9]{6}"
                        minLength={6} maxLength={6} disabled={loading} value={code}
                        aria-describedby="production-code-help" aria-invalid={!!error}
                        onChange={(event) => setCode(event.target.value.replace(/[^0-9]/g, '').slice(0, 6))} />
                    <small id="production-code-help">Не передавайте свой код другим сотрудникам.</small>
                    <button type="submit" disabled={loading || code.length !== 6}>
                        {loading ? 'Проверяем код…' : 'Войти на участок'}
                    </button>
                </form>
                {(error || sessionError) && <p role="alert" className={styles.error}>{error || sessionError}</p>}
                <small>Без подключения к сети изменения не записываются.</small>
            </section>
        </main>
    );
}
