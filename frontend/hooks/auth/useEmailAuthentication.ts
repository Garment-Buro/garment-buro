import {
    useCallback,
    useEffect,
    useRef,
    useState,
    type ClipboardEvent,
    type KeyboardEvent,
} from 'react';

import { requestAuthEmailCode } from '@/lib/api/auth';
import { normalizeOtpDigit } from '@/lib/auth/utils/auth';
import type { AuthStep } from '@/lib/auth/types';
import { useAuthStore } from '@/store/authStore';

export const useEmailAuthentication = () => {
    const authenticate = useAuthStore(state => state.authenticate);
    const [step, setStep] = useState<AuthStep>('input');
    const [email, setEmail] = useState('');
    const [code, setCode] = useState(['', '', '', '']);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [timer, setTimer] = useState(0);
    const requestRef = useRef<AbortController | null>(null);
    const firstInputRef = useRef<HTMLInputElement>(null);
    const secondInputRef = useRef<HTMLInputElement>(null);
    const thirdInputRef = useRef<HTMLInputElement>(null);
    const fourthInputRef = useRef<HTMLInputElement>(null);
    const inputRefs = [firstInputRef, secondInputRef, thirdInputRef, fourthInputRef];

    useEffect(() => () => { requestRef.current?.abort(); }, []);

    useEffect(() => {
        if (timer <= 0) return;
        const timeout = window.setTimeout(() => setTimer(value => value - 1), 1000);
        return () => window.clearTimeout(timeout);
    }, [timer]);

    const sendCode = useCallback(async () => {
        if (!email.trim() || requestRef.current || timer > 0) return;
        const controller = new AbortController();
        requestRef.current = controller;
        setLoading(true);
        setError('');
        try {
            await requestAuthEmailCode(email.trim(), controller.signal);
            if (controller.signal.aborted) return;
            setStep('verify');
            setCode(['', '', '', '']);
            setTimer(60);
            window.requestAnimationFrame(() => firstInputRef.current?.focus());
        } catch (requestError) {
            if (controller.signal.aborted) return;
            setError(requestError instanceof TypeError ? 'Ошибка сети' : 'Ошибка при отправке кода');
        } finally {
            if (requestRef.current === controller) {
                requestRef.current = null;
                setLoading(false);
            }
        }
    }, [email, timer]);

    const verifyCode = useCallback(async (finalCode?: string) => {
        const verificationCode = finalCode || code.join('');
        if (!/^\d{4}$/.test(verificationCode) || requestRef.current) return;
        const controller = new AbortController();
        requestRef.current = controller;
        setLoading(true);
        setError('');
        try {
            await authenticate(email.trim(), verificationCode, controller.signal);
        } catch (requestError) {
            if (controller.signal.aborted) return;
            setError(requestError instanceof TypeError ? 'Ошибка сети' : 'Неверный код');
        } finally {
            if (requestRef.current === controller) {
                requestRef.current = null;
                setLoading(false);
            }
        }
    }, [code, email, authenticate]);

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

    const showInputStep = () => {
        requestRef.current?.abort();
        requestRef.current = null;
        setLoading(false);
        setError('');
        setCode(['', '', '', '']);
        setStep('input');
    };

    return {
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
        verifyCode,
        changeOtp,
        handleOtpKeyDown,
        handleOtpPaste,
    };
};

