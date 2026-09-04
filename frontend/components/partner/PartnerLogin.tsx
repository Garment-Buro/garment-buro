"use client";

import { useEmailAuthentication } from '@/hooks/auth/useEmailAuthentication';
import { useAuthStore } from '@/store/authStore';

export const PartnerLogin = () => {
    const setAuth = useAuthStore(state => state.setAuth);
    const auth = useEmailAuthentication(setAuth);

    return (
        <div className="mx-auto grid min-h-dvh max-w-[1200px] items-center px-6 py-16 lg:grid-cols-2 lg:px-8">
            <section className="max-w-xl py-12">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-black/50">
                    GARMENT BURO · Партнёры
                </p>
                <h1 className="mt-6 max-w-lg text-4xl font-semibold leading-[1.08] tracking-[-0.04em] text-black sm:text-5xl lg:text-6xl">
                    Продажи по вашим ссылкам в одном кабинете
                </h1>
                <p className="mt-6 max-w-md text-base leading-7 text-black/60">
                    Статистика переходов, подтверждённые заказы, начисления и заявки на выплату.
                </p>
            </section>

            <section className="rounded-3xl border border-black/10 bg-white p-6 shadow-sm sm:p-10">
                {auth.step === 'input' ? (
                    <form
                        className="space-y-6"
                        onSubmit={event => {
                            event.preventDefault();
                            void auth.sendCode();
                        }}
                    >
                        <div>
                            <h2 className="text-2xl font-semibold tracking-[-0.03em] text-black">
                                Войти в кабинет
                            </h2>
                            <p className="mt-2 text-sm leading-6 text-black/50">
                                Используйте почту, на которую оформлен партнёрский доступ.
                            </p>
                        </div>
                        <label className="block">
                            <span className="mb-2 block text-sm font-medium text-black/70">Почта</span>
                            <input
                                type="email"
                                autoComplete="email"
                                required
                                value={auth.email}
                                onChange={event => auth.setEmail(event.target.value)}
                                placeholder="name@example.com"
                                className="h-12 w-full rounded-xl border border-black/15 bg-white px-4 text-base outline-none transition focus:border-black focus:ring-2 focus:ring-black/10"
                            />
                        </label>
                        {auth.error && <p className="text-sm text-red-700">{auth.error}</p>}
                        <button
                            type="submit"
                            disabled={!auth.email || auth.loading}
                            className="h-12 w-full rounded-xl bg-black px-5 text-sm font-semibold text-white transition hover:bg-black/80 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                            {auth.loading ? 'Отправляем код…' : 'Получить код'}
                        </button>
                    </form>
                ) : (
                    <div className="space-y-6">
                        <div>
                            <button
                                type="button"
                                onClick={auth.showInputStep}
                                className="text-sm text-black/50 transition hover:text-black"
                            >
                                ← Изменить почту
                            </button>
                            <h2 className="mt-5 text-2xl font-semibold tracking-[-0.03em] text-black">
                                Введите код
                            </h2>
                            <p className="mt-2 text-sm leading-6 text-black/50">
                                Отправили четыре цифры на {auth.email}
                            </p>
                        </div>
                        <div className="flex gap-3" onPaste={auth.handleOtpPaste}>
                            {auth.code.map((digit, index) => (
                                <input
                                    key={index}
                                    ref={auth.inputRefs[index]}
                                    value={digit}
                                    onChange={event => auth.changeOtp(index, event.target.value)}
                                    onKeyDown={event => auth.handleOtpKeyDown(index, event)}
                                    inputMode="numeric"
                                    autoComplete={index === 0 ? 'one-time-code' : 'off'}
                                    aria-label={`Цифра ${index + 1}`}
                                    className="h-14 min-w-0 flex-1 rounded-xl border border-black/15 text-center text-xl font-semibold outline-none transition focus:border-black focus:ring-2 focus:ring-black/10"
                                    maxLength={1}
                                />
                            ))}
                        </div>
                        {auth.error && <p className="text-sm text-red-700">{auth.error}</p>}
                        <div className="flex items-center justify-between gap-4">
                            <p className="text-sm text-black/45">
                                {auth.timer > 0 ? `Повтор через ${auth.timer} сек.` : 'Код можно отправить ещё раз'}
                            </p>
                            <button
                                type="button"
                                onClick={() => void auth.sendCode()}
                                disabled={auth.timer > 0 || auth.loading}
                                className="text-sm font-semibold text-black disabled:opacity-30"
                            >
                                Отправить снова
                            </button>
                        </div>
                    </div>
                )}
            </section>
        </div>
    );
};
