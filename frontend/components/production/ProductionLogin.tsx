'use client';
import { useEmailAuthentication } from '@/hooks/auth/useEmailAuthentication';
import { useAuthStore } from '@/store/authStore';
import styles from './ProductionTerminal.module.css';

export function ProductionLogin() {
    const setAuth = useAuthStore((state) => state.setAuth);
    const auth = useEmailAuthentication(setAuth);
    return (
        <main className={styles.login}>
            <section className={styles.panel}>
                <p className={styles.eyebrow}>GARMENT BURO · ПРОИЗВОДСТВО</p>
                <h1>Вход на участок</h1>
                <p>
                    Войдите с рабочей почтой. Доступ к операциям назначает
                    руководитель производства.
                </p>
                {auth.step === 'input' ? (
                    <form
                        onSubmit={(event) => {
                            event.preventDefault();
                            void auth.sendCode();
                        }}
                    >
                        <label>
                            Рабочая почта
                            <input
                                required
                                type="email"
                                autoComplete="email"
                                value={auth.email}
                                onChange={(event) =>
                                    auth.setEmail(event.target.value)
                                }
                            />
                        </label>
                        <button disabled={auth.loading} type="submit">
                            {auth.loading ? 'Отправляем…' : 'Получить код'}
                        </button>
                    </form>
                ) : (
                    <div>
                        <p>Введите код из письма на {auth.email}</p>
                        <div
                            className={styles.row}
                            onPaste={auth.handleOtpPaste}
                        >
                            {auth.code.map((digit, index) => (
                                <input
                                    key={index}
                                    aria-label={`Цифра ${index + 1}`}
                                    ref={auth.inputRefs[index]}
                                    value={digit}
                                    onChange={(event) =>
                                        auth.changeOtp(
                                            index,
                                            event.target.value,
                                        )
                                    }
                                    onKeyDown={(event) =>
                                        auth.handleOtpKeyDown(index, event)
                                    }
                                    inputMode="numeric"
                                    autoComplete={
                                        index === 0 ? 'one-time-code' : 'off'
                                    }
                                    maxLength={1}
                                />
                            ))}
                        </div>
                        <button onClick={auth.showInputStep}>
                            Изменить почту
                        </button>
                        <button
                            disabled={auth.timer > 0 || auth.loading}
                            onClick={() => void auth.sendCode()}
                        >
                            {auth.timer > 0
                                ? `Повтор через ${auth.timer} сек.`
                                : 'Отправить снова'}
                        </button>
                    </div>
                )}
                {auth.error && (
                    <p role="alert" className={styles.error}>
                        {auth.error}
                    </p>
                )}
                <small>Без подключения к сети изменения не записываются.</small>
            </section>
        </main>
    );
}
