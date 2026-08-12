type AuthCloseButtonProps = {
    onClick: () => void;
};

export const AuthCloseButton = ({ onClick }: AuthCloseButtonProps) => (
    <button
        onClick={onClick}
        className="absolute top-[40px] right-[40px] z-20 w-8 h-8 flex items-center justify-center rounded-full hover:bg-black/5 transition-colors text-[#ABABAB]"
        aria-label="Закрыть"
    >
        <svg width="20" height="20" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 4L4 12M4 4L12 12" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    </button>
);

