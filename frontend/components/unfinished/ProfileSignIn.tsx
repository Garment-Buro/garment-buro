'use client';

import { useEmailAuthentication } from '@/hooks/auth/useEmailAuthentication';
import styles from './UnfinishedSurface.module.css';

export function ProfileSignIn() {
    const auth = useEmailAuthentication();
    const verifying = auth.step === 'verify';
    return (
        <form className={styles.profileSettingsCard} onSubmit={event => {
            event.preventDefault();
            if (verifying) void auth.verifyCode();
            else void auth.sendCode();
        }}>
            <h2>Вход</h2>
            <label className={styles.profileField}>
                <span>Почта</span>
                <input type="email" required maxLength={320} value={auth.email} autoComplete="email"
                    disabled={auth.loading || verifying} onChange={event => auth.setEmail(event.target.value)} />
            </label>
            {verifying && <>
                <p className={styles.profileMessage}>Введите код из письма.</p>
                <div className={styles.profileCodeSlots} aria-label="Код из письма">
                    {auth.code.map((character, index) => (
                        <input key={index} ref={auth.inputRefs[index]} type="text" inputMode="numeric"
                            autoComplete={index === 0 ? 'one-time-code' : 'off'} value={character} maxLength={1}
                            aria-label={`Цифра кода ${index + 1}`} disabled={auth.loading}
                            onChange={event => auth.changeOtp(index, event.target.value)}
                            onPaste={auth.handleOtpPaste} onKeyDown={event => auth.handleOtpKeyDown(index, event)} />
                    ))}
                </div>
                <button className={styles.profileResendButton} type="button" disabled={auth.loading || auth.timer > 0}
                    onClick={() => void auth.sendCode()}>
                    {auth.timer > 0 ? `Отправить снова (${auth.timer} с)` : 'Отправить снова'}
                </button>
                <button className={styles.profileResendButton} type="button" onClick={auth.showInputStep}>Изменить почту</button>
            </>}
            {auth.error && <p role="alert" className={styles.profileMessage}>{auth.error}</p>}
            <button className={styles.profilePrimaryButton} type="submit"
                disabled={auth.loading || (verifying ? auth.code.some(character => !character) : !auth.email.trim() || auth.timer > 0)}>
                {auth.loading ? 'ПОДОЖДИТЕ…' : verifying ? 'ВОЙТИ' : 'ПОЛУЧИТЬ КОД'}
            </button>
            <p className={styles.profileConsentText}>
                Нажимая на кнопку, вы подтверждаете, что ознакомлены
                с Соглашением о конфиденциальности и разрешаете использовать персональные данные
            </p>
        </form>
    );
}
