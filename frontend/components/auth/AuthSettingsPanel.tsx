import { useAuthSettings } from '@/hooks/auth/useAuthSettings';
import { useEmailLinker } from '@/hooks/auth/useEmailLinker';
import type { AuthUser } from '@/lib/auth/types';

import { Button } from '@/components/shared/Button';
import { Text } from '@/components/shared/Text';

type UpdateUser = (user: AuthUser) => void;

type EmailLinkerProps = {
    user: AuthUser | null;
    token: string | null;
    updateUser: UpdateUser;
};

const EmailLinker = ({ user, token, updateUser }: EmailLinkerProps) => {
    const emailLinker = useEmailLinker({ token, updateUser });

    if (user?.email) {
        return <input value={user.email} disabled className="w-full bg-transparent outline-none text-[16px] text-[#898989] cursor-not-allowed" />;
    }

    if (emailLinker.step === 'start') {
        return (
            <button onClick={emailLinker.start} className="text-left text-[#0088CC] underline font-manrope text-[14px]">
                Привязать почту
            </button>
        );
    }

    if (emailLinker.step === 'input') {
        return (
            <div className="flex flex-col gap-2">
                <div className="flex gap-2">
                    <input
                        value={emailLinker.email}
                        onChange={event => emailLinker.setEmail(event.target.value)}
                        placeholder="example@mail.ru"
                        className="w-full bg-transparent outline-none text-[16px] text-black border-b border-[#ABABAB] focus:border-black"
                    />
                    <button
                        onClick={emailLinker.sendCode}
                        disabled={!emailLinker.email || emailLinker.loading}
                        className="px-3 py-1 bg-black text-white text-sm rounded disabled:opacity-50"
                    >
                        Отправить
                    </button>
                </div>
                {emailLinker.error && <Text className="text-red-500 text-sm">{emailLinker.error}</Text>}
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-2">
            <Text size={14} className="text-[#A0A0A0]">Код отправлен на {emailLinker.email}</Text>
            <div className="flex gap-2 items-center">
                <input
                    value={emailLinker.code}
                    onChange={event => emailLinker.changeCode(event.target.value)}
                    placeholder="1234"
                    className="w-[80px] text-center bg-transparent outline-none text-[16px] text-black border-b border-[#ABABAB] focus:border-black tracking-widest"
                />
                <button
                    onClick={emailLinker.verifyCode}
                    disabled={emailLinker.code.length !== 4 || emailLinker.loading}
                    className="px-3 py-1 bg-black text-white text-sm rounded disabled:opacity-50"
                >
                    Подтвердить
                </button>
            </div>
            {emailLinker.error && <Text className="text-red-500 text-sm">{emailLinker.error}</Text>}
        </div>
    );
};

type AuthSettingsPanelProps = {
    user: AuthUser | null;
    token: string | null;
    updateUser: UpdateUser;
    logout: () => void | Promise<void>;
};

export const AuthSettingsPanel = ({ user, token, updateUser, logout }: AuthSettingsPanelProps) => {
    const settings = useAuthSettings({ user, token, updateUser, logout });

    return (
        <div className="flex flex-col gap-6">
            <div className="flex flex-col gap-8 bg-white p-6 rounded-[15px]">
                <div className="flex flex-col gap-6">
                    <Text className="text-[12px] text-[#A0A0A0] uppercase tracking-wider font-semibold">Личная информация</Text>
                    <div className="flex flex-col gap-1 border-b border-[#F0F0F0] pb-2">
                        <Text className="text-[18px] font-bold text-black">Имя профиля</Text>
                        <input
                            value={settings.profile.first_name}
                            onChange={event => settings.setProfileField('first_name', event.target.value)}
                            className="w-full bg-transparent outline-none text-[16px] text-[#898989] placeholder:text-[#898989]"
                            placeholder="Не указано"
                        />
                    </div>
                    <div className="flex flex-col gap-1 border-b border-[#F0F0F0] pb-2">
                        <Text className="text-[18px] font-bold text-black">Пол</Text>
                        <select
                            value={settings.profile.gender}
                            onChange={event => settings.setProfileField('gender', event.target.value)}
                            className="w-full bg-transparent outline-none text-[16px] text-[#898989] appearance-none"
                        >
                            <option value="">Не выбран</option>
                            <option value="male">Мужской</option>
                            <option value="female">Женский</option>
                        </select>
                    </div>
                </div>
                <div className="flex flex-col gap-6">
                    <Text className="text-[12px] text-[#A0A0A0] uppercase tracking-wider font-semibold">Контакты</Text>
                    <div className="flex flex-col gap-1 border-b border-[#F0F0F0] pb-2">
                        <Text className="text-[18px] font-bold text-black">Телефон</Text>
                        <input
                            value={settings.profile.phone}
                            onChange={event => settings.setProfileField('phone', event.target.value)}
                            className="w-full bg-transparent outline-none text-[16px] text-[#898989] placeholder:text-[#898989]"
                            placeholder="+7 000 000 00 00"
                        />
                    </div>
                    <div className="flex flex-col gap-1 border-b border-[#F0F0F0] pb-2">
                        <Text className="text-[18px] font-bold text-black">Почта</Text>
                        <EmailLinker user={user} token={token} updateUser={updateUser} />
                    </div>
                </div>
                <div className="flex justify-start">
                    <Button
                        onClick={settings.saveProfile}
                        isLoading={settings.saving}
                        className="bg-black text-white rounded-[10px] px-8 h-[45px] text-[14px] uppercase font-bold"
                    >
                        Сохранить
                    </Button>
                </div>
            </div>
            <div className="bg-white rounded-[15px] overflow-hidden">
                <button onClick={logout} className="w-full p-6 text-left hover:bg-black/[0.02] transition-colors">
                    <Text className="text-[18px] font-bold text-black">Выйти из профиля</Text>
                </button>
            </div>
            <div className="bg-white rounded-[15px] overflow-hidden">
                <button onClick={settings.removeProfile} className="w-full p-6 text-left hover:bg-black/[0.02] transition-colors">
                    <Text className="text-[18px] font-bold text-[#FF3B30]">Удалить аккаунт</Text>
                </button>
            </div>
        </div>
    );
};
