import {
    useCallback,
    useEffect,
    useRef,
    useState,
    type ClipboardEvent,
    type KeyboardEvent,
} from 'react';

import { requestAuthEmailCode, verifyAuthEmailCode } from '@/lib/api/auth';
import { normalizeOtpDigit } from '@/lib/auth/utils/auth';
import type { AuthMethod, AuthStep, AuthUser } from '@/lib/auth/types';

type SetAuth = (token: string, user: AuthUser) => void;

export const useEmailAuthentication = (setAuth: SetAuth) => {
    const [method, setMethod] = useState<AuthMethod>('email');
    const [step, setStep] = useState<AuthStep>('input');
    const [email, setEmail] = useState('');
    const [code, setCode] = useState(['', '', '', '']);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [timer, setTimer] = useState(0);
    const firstInputRef = useRef<HTMLInputElement>(null);
    const secondInputRef = useRef<HTMLInputElement>(null);
    const thirdInputRef = useRef<HTMLInputElement>(null);
    const fourthInputRef = useRef<HTMLInputElement>(null);
    const inputRefs = [firstInputRef, secondInputRef, thirdInputRef, fourthInputRef];

    useEffect(() => {
        if (timer <= 0) return;
        const timeout = window.setTimeout(() => setTimer(value => value - 1), 1000);
        return () => window.clearTimeout(timeout);
    }, [timer]);

    const sendCode = useCallback(async () => {
        if (!email) return;
        setLoading(true);
        setError('');
        try {
            const data = await requestAuthEmailCode(email);
            setStep('verify');
            setTimer(59);
            if (data.testing_only_otp) {
                console.log(`%c[AUTH] Ваш код: ${data.testing_only_otp}`, 'color: #0088CC; font-weight: bold; font-size: 14px;');
            }
        } catch (requestError) {
            setError(requestError instanceof TypeError ? 'Ошибка сети' : 'Ошибка при отправке кода');
        } finally {
            setLoading(false);
        }
    }, [email]);

    const verifyCode = useCallback(async (finalCode?: string) => {
        const verificationCode = finalCode || code.join('');
        if (verificationCode.length !== 4) return;
        setLoading(true);
        setError('');
        try {
            const data = await verifyAuthEmailCode(email, verificationCode);
            setAuth(data.token, data.user);
        } catch (requestError) {
            setError(requestError instanceof TypeError ? 'Ошибка сети' : 'Неверный код');
        } finally {
            setLoading(false);
        }
    }, [code, email, setAuth]);

    const changeOtp = (index: number, value: string) => {
        if (!/^\d*$/.test(value)) return;
        const nextCode = [...code];
        nextCode[index] = normalizeOtpDigit(value);
        setCode(nextCode);
        if (value && index < inputRefs.length - 1) inputRefs[index + 1].current?.focus();
        if (nextCode.every(Boolean)) void verifyCode(nextCode.join(''));
    };

    const handleOtpKeyDown = (index: number, event: KeyboardEvent<HTMLInputElement>) => {
        if (event.key === 'Backspace' && !code[index] && index > 0) {
            inputRefs[index - 1].current?.focus();
        }
    };

    const handleOtpPaste = (event: ClipboardEvent<HTMLInputElement>) => {
        event.preventDefault();
        const pastedCode = event.clipboardData.getData('text').slice(0, 4);
        if (!/^\d+$/.test(pastedCode)) return;
        const nextCode = [...code];
        pastedCode.split('').forEach((character, index) => {
            if (index < nextCode.length) nextCode[index] = character;
        });
        setCode(nextCode);
        if (nextCode.every(Boolean)) void verifyCode(nextCode.join(''));
    };

    const showInputStep = () => setStep('input');

    return {
        method,
        setMethod,
        step,
        showInputStep,
        email,
        setEmail,
        code,
        loading,
        error,
        timer,
        inputRefs,
        sendCode,
        changeOtp,
        handleOtpKeyDown,
        handleOtpPaste,
    };
};

