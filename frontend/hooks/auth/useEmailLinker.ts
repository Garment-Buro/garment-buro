import { useState } from 'react';

import { requestAuthEmailLink, verifyAuthEmailLink } from '@/lib/api/auth';
import type { AuthUser, EmailLinkStep } from '@/lib/auth/types';
import { hasUsableAuthToken, normalizeOtpCode } from '@/lib/auth/utils/auth';
import { useAuthStore } from '@/store/authStore';

type UseEmailLinkerOptions = {
    token: string | null;
    updateUser: (user: AuthUser) => void;
};

export const useEmailLinker = ({ token, updateUser }: UseEmailLinkerOptions) => {
    const [step, setStep] = useState<EmailLinkStep>('start');
    const [email, setEmail] = useState('');
    const [code, setCode] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const runAuthenticated = useAuthStore(state => state.runAuthenticated);

    const start = () => setStep('input');
    const changeCode = (value: string) => setCode(normalizeOtpCode(value));

    const sendCode = async () => {
        if (!hasUsableAuthToken(token) || !email) return;
        setLoading(true);
        setError('');
        try {
            await runAuthenticated(
                authToken => requestAuthEmailLink(authToken, email),
            );
            setStep('verify');
        } catch (requestError) {
            setError(requestError instanceof TypeError ? 'Ошибка сети' : requestError instanceof Error ? requestError.message : 'Ошибка');
        } finally {
            setLoading(false);
        }
    };

    const verifyCode = async () => {
        if (!hasUsableAuthToken(token) || code.length !== 4) return;
        setLoading(true);
        setError('');
        try {
            updateUser(await runAuthenticated(
                authToken => verifyAuthEmailLink(authToken, email, code),
            ));
        } catch (requestError) {
            setError(requestError instanceof TypeError ? 'Ошибка сети' : 'Неверный код');
        } finally {
            setLoading(false);
        }
    };

    return {
        step,
        start,
        email,
        setEmail,
        code,
        changeCode,
        loading,
        error,
        sendCode,
        verifyCode,
    };
};
