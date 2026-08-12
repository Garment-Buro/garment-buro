export const Divider = ({ className = '' }: { className?: string }) => {
    return (
        <div
            className={`w-full h-[4px] rounded-[3px] bg-[rgba(151,151,151,0.26)] ${className}`}
            role="separator"
        />
    );
};
