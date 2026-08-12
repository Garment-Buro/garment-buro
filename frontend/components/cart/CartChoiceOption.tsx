import type { ReactNode } from 'react';

type CartChoiceOptionProps = {
    active: boolean;
    label: string;
    primary: ReactNode;
    secondary: ReactNode;
    onSelect: () => void;
    variant: 'delivery' | 'payment';
};

const CartChoiceRadio = ({ active }: { active: boolean }) => (
    active ? (
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="7" r="7" fill="#717171" />
            <circle cx="7" cy="7" r="2" fill="#ECECEC" />
        </svg>
    ) : (
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="7" r="6.5" stroke="#A6A6A6" />
        </svg>
    )
);

export const CartChoiceOption = ({
    active,
    label,
    primary,
    secondary,
    onSelect,
    variant,
}: CartChoiceOptionProps) => {
    const isDelivery = variant === 'delivery';

    return (
        <button
            type="button"
            onClick={onSelect}
            aria-pressed={active}
            className={isDelivery
                ? 'flex flex-1 items-start gap-[9px] border-0 text-left'
                : 'flex min-h-[34px] flex-1 items-start gap-[9px] rounded-[3px] px-[clamp(8px,2.162vw,14px)] py-[clamp(8px,2.162vw,14px)] text-left'}
            style={isDelivery ? {
                borderRadius: 3,
                background: active ? '#ECECEC' : 'transparent',
                padding: 'clamp(8px, 2.162vw, 14px) clamp(8px, 2.162vw, 14px) clamp(10px, 2.703vw, 17px)',
                cursor: 'pointer',
            } : { background: active ? '#ECECEC' : 'transparent' }}
        >
            <div className="shrink-0 pt-[1px]">
                <CartChoiceRadio active={active} />
            </div>
            <div className="flex min-w-0 flex-col gap-[3px]">
                {isDelivery ? (
                    <span style={{
                        color: '#797979',
                        fontFamily: 'var(--font-manrope), Manrope, sans-serif',
                        fontSize: 10,
                        fontWeight: 500,
                        lineHeight: 'normal',
                    }}>
                        {label}
                    </span>
                ) : (
                    <span className="text-[10px] font-medium leading-normal text-[#797979]">{label}</span>
                )}
                {isDelivery ? (
                    <div className="flex items-center whitespace-nowrap" style={{ gap: 3 }}>
                        <span style={{
                            color: '#2D2D2D',
                            fontFamily: 'var(--font-manrope), Manrope, sans-serif',
                            fontSize: 10,
                            fontWeight: 700,
                            lineHeight: 'normal',
                        }}>
                            {primary}
                        </span>
                        <span style={{
                            color: '#2D2D2D',
                            fontFamily: 'var(--font-manrope), Manrope, sans-serif',
                            fontSize: 10,
                            fontWeight: 500,
                            lineHeight: 'normal',
                        }}>
                            {secondary}
                        </span>
                    </div>
                ) : (
                    <div className="flex items-center whitespace-nowrap gap-[3px] text-[10px] leading-normal text-[#2D2D2D]">
                        <span className="font-bold">{primary}</span>
                        <span className="font-medium">{secondary}</span>
                    </div>
                )}
            </div>
        </button>
    );
};
