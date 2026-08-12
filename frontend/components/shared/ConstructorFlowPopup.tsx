"use client";

import { Popup } from "@/components/shared/Popup";

type CatalogHintPopupProps = {
    isOpen: boolean;
    onBack: () => void;
    onContinue: () => void;
};

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
}: {
    children: React.ReactNode;
    onClick: () => void;
}) => (
    <button
        type="button"
        onClick={onClick}
        className={`${EXIT_POPUP_BUTTON_BASE_CLASS} text-[#676767] shadow-[0_0.934px_1.681px_0_rgba(0,0,0,0.26)]`}
    >
        {children}
    </button>
);

export function CatalogHintPopup({ isOpen, onBack, onContinue }: CatalogHintPopupProps) {
    if (!isOpen) return null;

    return (
        <Popup
            onClose={onBack}
            showClose={false}
            maxWidth={330}
            panelClassName="bg-[#fff]"
            viewportStyle={CONSTRUCTOR_POPUP_VIEWPORT_STYLE}
            backdropClassName="bg-black/50"
        >
            <div className="flex h-[255px] flex-col items-center px-[15px] pt-[50px] pb-[25px] text-center font-manrope">
                <p className="text-[12px] font-medium leading-normal text-[#A0A0A0] [leading-trim:both] [text-edge:cap]">Выберите вещь из каталога</p>
                <p className="mt-[8px] text-[10px] font-medium leading-normal text-[#A0A0A0] [leading-trim:both] [text-edge:cap]">
                    нажмите на иконку шестеренки,<br />
                    чтобы редактировать ее
                </p>
                <p className="mt-[25px] text-[16px] font-medium leading-normal text-[#2D2D2D] [leading-trim:both] [text-edge:cap]">
                    Перейти к выбору?
                </p>
                <ExitPopupButtons>
                    <ExitPopupButton onClick={onBack}>НАЗАД</ExitPopupButton>
                    <ExitPopupButton onClick={onContinue}>ДАЛЕЕ</ExitPopupButton>
                </ExitPopupButtons>
            </div>
        </Popup>
    );
}

export function UnfinishedDeletePopup({ isOpen, onClose, onConfirm }: UnfinishedDeletePopupProps) {
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
                    Вы уверены, что хотите удалить?
                </p>
                <p className="mt-[8px] text-[10px] font-medium leading-normal text-[#A0A0A0] [leading-trim:both] [text-edge:cap]">
                    После удаления черновик<br />
                    нельзя будет восстановить
                </p>
                <p className="mt-[25px] text-[16px] font-medium leading-normal text-[#2D2D2D] [leading-trim:both] [text-edge:cap]">
                    Удалить черновик?
                </p>
                <ExitPopupButtons>
                    <ExitPopupButton onClick={onClose}>ОТМЕНА</ExitPopupButton>
                    <ExitPopupButton onClick={onConfirm}>УДАЛИТЬ</ExitPopupButton>
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
