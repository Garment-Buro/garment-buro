import Image from 'next/image';

import { useEmailAuthentication } from '@/hooks/auth/useEmailAuthentication';
import type { AuthMethod, AuthUser } from '@/lib/auth/types';

import { Text } from '@/components/shared/Text';
import { AuthCloseButton } from './AuthCloseButton';

type AuthenticationPanelProps = {
    onClose: () => void;
    setAuth: (token: string, user: AuthUser) => void;
};

const AuthenticationMethodTabs = ({ method, onChange }: {
    method: AuthMethod;
    onChange: (method: AuthMethod) => void;
}) => (
    <div className="flex gap-10 mb-[40px] border-b border-black/5 relative">
        {([
            ['email', 'По почте'],
            ['telegram', 'Через Telegram'],
        ] as const).map(([value, label]) => (
            <button
                key={value}
                onClick={() => onChange(value)}
                className={`pb-[5px] text-[16px] font-manrope transition-all relative text-black ${method === value ? 'font-bold' : 'font-normal opacity-60'}`}
            >
                {label}
                {method === value && <div className="absolute -bottom-px left-0 w-full h-px bg-black" />}
            </button>
        ))}
    </div>
);

export const AuthenticationPanel = ({ onClose, setAuth }: AuthenticationPanelProps) => {
    const {
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
    } = useEmailAuthentication(setAuth);

    return (
        <div className="flex w-full">
            <div className="w-full md:w-[680px] md:h-[630px] px-6 py-6 md:px-[75px] md:py-[45px] flex flex-col bg-white rounded-[19px] relative">
                <AuthCloseButton onClick={onClose} />

                {step === 'input' ? (
                    <>
                        <Text size={24} className="mb-5 md:mb-[40px] text-black font-semibold">Вход/Регистрация</Text>
                        <AuthenticationMethodTabs method={method} onChange={setMethod} />

                        {method === 'email' ? (
                            <div className="flex flex-col gap-5 md:gap-8">
                                <div className="flex flex-col gap-2">
                                    <Text className="text-[#898989] text-[16px]">Электронная почта</Text>
                                    <input
                                        placeholder="template@garment-buro.ru"
                                        value={email}
                                        onChange={event => setEmail(event.target.value)}
                                        className="h-[40px] text-[16px] outline-none border-b border-[#ABABAB] focus:border-black transition-all bg-transparent"
                                    />
                                </div>
                                {error && <Text size={14} className="text-red-500">{error}</Text>}
                                <button
                                    onClick={sendCode}
                                    disabled={loading || !email}
                                    className="w-full h-[55px] rounded-[12px] shadow-[0_2px_10px_rgba(0,0,0,0.05)] bg-[linear-gradient(180deg,#FFFFFF_0%,#F0F0F0_100%)] border border-white/80 active:translate-y-px transition-transform flex items-center justify-center cursor-pointer text-black font-manrope text-[16px] disabled:opacity-50 disabled:pointer-events-none"
                                >
                                    {loading ? 'Загрузка...' : 'Войти'}
                                </button>
                            </div>
                        ) : (
                            <div className="flex flex-col gap-4 py-4 md:py-8">
                                <button className="w-full h-[55px] rounded-[12px] bg-[#0088CC] text-white font-manrope text-[16px] flex items-center justify-center gap-3 active:translate-y-px transition-transform cursor-pointer">
                                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                        <path d="M11.944 0C5.346 0 0 5.346 0 11.944c0 6.598 5.346 11.944 11.944 11.944s11.944-5.346 11.944-11.944C23.888 5.346 18.542 0 11.944 0zm5.66 8.161l-1.928 9.09c-.147.662-.538.825-.992.57l-2.937-2.164-1.416 1.363c-.156.156-.288.288-.588.288l.21-2.98 5.426-4.903c.236-.209-.052-.326-.367-.116l-6.703 4.22-2.888-.903c-.628-.196-.64-.628.13-.93l11.293-4.352c.523-.19.98.125.76.815z" fill="white" />
                                    </svg>
                                    Войти через Telegram
                                </button>
                                <Text size={14} className="text-center text-[#A0A0A0]">Авторизация через официальный виджет Telegram</Text>
                            </div>
                        )}

                        <div className="mt-auto flex justify-center">
                            <Text className="text-[#898989] text-[16px] leading-tight font-manrope text-center max-w-[445px] mb-0" variant="secondary">
                                Нажимая на кнопку, вы подтверждаете, что ознакомлены с <span className="underline cursor-pointer">Соглашением о конфиденциальности</span> и разрешаете использовать персональные данные
                            </Text>
                        </div>
                    </>
                ) : (
                    <div className="flex flex-col items-center justify-center h-full py-10">
                        <button
                            onClick={showInputStep}
                            className="absolute top-[40px] left-[40px] p-2 hover:bg-black/5 rounded-full transition-all text-[#ABABAB]"
                            aria-label="Вернуться к вводу почты"
                        >
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M19 12H5M5 12L12 19M5 12L12 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                        </button>

                        <Text size={24} className="mb-4 text-center text-black font-semibold">Введите код из письма</Text>
                        <Text size={14} className="text-[#A0A0A0] mb-12 text-center">Мы отправили его на почту {email}</Text>
                        <div className="flex gap-[10px] mb-10">
                            {code.map((digit, index) => (
                                <div key={index} className="flex flex-col items-center gap-1">
                                    <input
                                        ref={inputRefs[index]}
                                        type="text"
                                        maxLength={1}
                                        value={digit}
                                        onChange={event => changeOtp(index, event.target.value)}
                                        onKeyDown={event => handleOtpKeyDown(index, event)}
                                        onPaste={handleOtpPaste}
                                        className="w-[40px] h-[30px] bg-transparent text-center text-[24px] font-bold outline-none"
                                    />
                                    <div className={`w-[40px] h-[2px] rounded-[15px] transition-all ${digit || inputRefs[index].current === document.activeElement ? 'bg-black' : 'bg-[#ABABAB]'}`} />
                                </div>
                            ))}
                        </div>
                        {timer > 0 ? (
                            <Text size={14} className="text-[#A0A0A0]">Новый код можно получить через {Math.floor(timer / 60)}:{(timer % 60).toString().padStart(2, '0')}</Text>
                        ) : (
                            <button onClick={sendCode} className="text-black text-[14px] underline font-medium">Отправить код еще раз</button>
                        )}
                        {error && <Text size={14} className="text-red-500 mt-6">{error}</Text>}
                    </div>
                )}
            </div>
            <div className="hidden lg:block w-[295px] h-[630px] bg-[#E5E5E5] rounded-[19px] relative overflow-hidden">
                <Image src="/login_panel_right.webp" alt="Auth decor" fill className="object-cover" priority />
            </div>
        </div>
    );
};

