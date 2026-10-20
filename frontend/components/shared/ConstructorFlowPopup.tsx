"use client";

import { Popup } from "@/components/shared/Popup";

type ConstructorExitPopupProps = {
    isOpen: boolean;
    onClose: () => void;
    onLeave: () => void;
    onSave: () => void;
};

type UnfinishedDeletePopupProps = {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => void;
    busy?: boolean;
    error?: string | null;
};

const CONSTRUCTOR_POPUP_VIEWPORT_STYLE = {
    position: "fixed",
    inset: 0,
    width: "100%",
} as const;

const ExitPopupButtons = ({ children }: { children: React.ReactNode }) => (
    <div className="mt-[30px] flex items-center justify-center gap-[5px]">
        {children}
    </div>
);

const EXIT_POPUP_BUTTON_BASE_CLASS = "flex h-[30px] w-[150px] items-center justify-center rounded-[5px] border-0 bg-[#FFF] p-0 text-center font-manrope text-[14px] font-semibold leading-[11.582px] transition active:scale-95 [leading-trim:both] [text-edge:cap]";

const ExitPopupButton = ({
    children,
    onClick,
    disabled = false,
}: {
    children: React.ReactNode;
    onClick: () => void;
    disabled?: boolean;
}) => (
    <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        className={`${EXIT_POPUP_BUTTON_BASE_CLASS} text-[#676767] shadow-[0_0.934px_1.681px_0_rgba(0,0,0,0.26)]`}
    >
        {children}
    </button>
);

export function UnfinishedDeletePopup({ isOpen, onClose, onConfirm, busy = false, error }: UnfinishedDeletePopupProps) {
    if (!isOpen) return null;

    return (
        <Popup
            onClose={onClose}
            showClose={false}
            maxWidth={330}
            panelClassName="bg-[#fff]"
            viewportStyle={CONSTRUCTOR_POPUP_VIEWPORT_STYLE}
            backdropClassName="bg-black/50"
        >
            <div className="flex min-h-[255px] flex-col items-center px-[15px] pt-[50px] pb-[25px] text-center font-manrope">
                <p className="text-[12px] font-medium leading-normal text-[#A0A0A0] [leading-trim:both] [text-edge:cap]">
                    Вы уверены, что хотите удалить?
                </p>
                <p className="mt-[8px] text-[10px] font-medium leading-normal text-[#A0A0A0] [leading-trim:both] [text-edge:cap]">
                    После удаления проект<br />
                    нельзя будет восстановить
                </p>
                <p className="mt-[25px] text-[16px] font-medium leading-normal text-[#2D2D2D] [leading-trim:both] [text-edge:cap]">
                    Удалить проект?
                </p>
                {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
                <ExitPopupButtons>
                    <ExitPopupButton onClick={onClose} disabled={busy}>ОТМЕНА</ExitPopupButton>
                    <ExitPopupButton onClick={onConfirm} disabled={busy}>{busy ? 'УДАЛЯЕМ…' : 'УДАЛИТЬ'}</ExitPopupButton>
                </ExitPopupButtons>
            </div>
        </Popup>
    );
}

export function ConstructorExitPopup({ isOpen, onClose, onLeave, onSave }: ConstructorExitPopupProps) {
    if (!isOpen) return null;

    return (
        <Popup
            onClose={onClose}
            showClose={false}
            maxWidth={330}
            panelClassName="bg-[#fff]"
            viewportStyle={CONSTRUCTOR_POPUP_VIEWPORT_STYLE}
            backdropClassName="bg-black/50"
        >
            <div className="flex h-[255px] flex-col items-center px-[15px] pt-[50px] pb-[25px] text-center font-manrope">
                <p className="text-[12px] font-medium leading-normal text-[#A0A0A0] [leading-trim:both] [text-edge:cap]">
                    Вы уверены, что хотите выйти?
                </p>
                <p className="mt-[8px] text-[10px] font-medium leading-normal text-[#A0A0A0] [leading-trim:both] [text-edge:cap]">
                    После выхода внесенные изменения<br />
                    не будут сохранены
                </p>
                <p className="mt-[25px] text-[16px] font-medium leading-normal text-[#2D2D2D] [leading-trim:both] [text-edge:cap]">
                    Сохранить в личном кабинете?
                </p>
                <ExitPopupButtons>
                    <ExitPopupButton onClick={onLeave}>НА ГЛАВНУЮ</ExitPopupButton>
                    <ExitPopupButton onClick={onSave}>СОХРАНИТЬ</ExitPopupButton>
                </ExitPopupButtons>
            </div>
        </Popup>
    );
}
