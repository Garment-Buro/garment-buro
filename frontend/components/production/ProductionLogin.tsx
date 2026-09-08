'use client';

import { useRef, useState } from 'react';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import styles from './ProductionTerminal.module.css';

export function ProductionLogin({ admin = false }: { admin?: boolean }) {
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
                <h1>{admin ? 'Вход администратора' : 'Вход в терминал'}</h1>
                <p>{admin ? 'Введите личный код администратора из 8 цифр.' : 'Введите личный код: 6 цифр для сотрудника или 8 для администратора.'} Код и доступ выдаёт руководитель.</p>
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
                    <label htmlFor="production-code">Личный код сотрудника</label>
                    <input id="production-code" type="password" inputMode="numeric"
                        autoComplete="current-password" required pattern={admin ? '99[0-9]{6}' : '([0-9]{6}|99[0-9]{6})'}
                        minLength={admin ? 8 : 6} maxLength={8} disabled={loading} value={code}
                        aria-describedby="production-code-help" aria-invalid={!!error}
                        onChange={(event) => setCode(event.target.value.replace(/[^0-9]/g, '').slice(0, 8))} />
                    <small id="production-code-help">Не передавайте свой код другим сотрудникам.</small>
                    <button type="submit" disabled={loading || !(admin ? /^99[0-9]{6}$/ : /^(?:[0-9]{6}|99[0-9]{6})$/).test(code)}>
                        {loading ? 'Проверяем код…' : 'Войти в терминал'}
                    </button>
                </form>
                {(error || sessionError) && <p role="alert" className={styles.error}>{error || sessionError}</p>}
                <small>Без подключения к сети изменения не записываются.</small>
            </section>
        </main>
    );
}
