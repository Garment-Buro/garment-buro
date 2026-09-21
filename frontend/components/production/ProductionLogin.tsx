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
                <h1>Вход в терминал</h1>
                <p className={styles.loginMessage}>
                    Твоя работа двигает заказ вперёд.
                </p>
                <form onSubmit={async (event) => {
                    event.preventDefault();
                    if (locked.current || !/^(?:[0-9]{6}|99[0-9]{6})$/.test(code)) return;
                    locked.current = true; setLoading(true); setError('');
                    try { await login(code); }
                    catch (failure) {
                        setError(failure instanceof Error ? failure.message : 'Не удалось войти');
                        setCode('');
                    } finally { locked.current = false; setLoading(false); }
                }}>
                    <label
                        className={styles.srOnly}
                        htmlFor="production-code"
                    >
                        Личный код сотрудника
                    </label>
                    <input id="production-code" type="password" inputMode="numeric"
                        autoComplete="current-password" required pattern="([0-9]{6}|99[0-9]{6})"
                        minLength={6} maxLength={8} disabled={loading} value={code}
                        placeholder="Личный код сотрудника"
                        aria-describedby="production-code-help" aria-invalid={!!error}
                        onChange={(event) => setCode(event.target.value.replace(/[^0-9]/g, '').slice(0, 8))} />
                    <small id="production-code-help">Не передавайте свой код другим сотрудникам.</small>
                    <button type="submit" disabled={loading || !/^(?:[0-9]{6}|99[0-9]{6})$/.test(code)}>
                        {loading ? 'Проверяем код…' : 'Войти в терминал'}
                    </button>
                </form>
                {(error || sessionError) && <p role="alert" className={styles.error}>{error || sessionError}</p>}
            </section>
        </main>
    );
}
