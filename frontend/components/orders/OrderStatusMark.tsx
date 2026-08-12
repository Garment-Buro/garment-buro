type OrderStatusMarkProps = {
    variant: 'success' | 'error';
};

export const OrderStatusMark = ({ variant }: OrderStatusMarkProps) => {
    if (variant === 'error') {
        return (
            <div className="w-[80px] h-[80px] mx-auto mb-4 flex items-center justify-center rounded-full bg-red-100 border-4 border-red-400">
                <svg width="36" height="36" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M10 10L26 26M26 10L10 26" stroke="#ef4444" strokeWidth="3.5" strokeLinecap="round" />
                </svg>
            </div>
        );
    }

    return (
        <div className="w-[80px] h-[115px] mx-auto">
            <div style={{
                width: 80, height: 80, position: 'relative',
                borderRadius: '50%', boxSizing: 'content-box',
                border: '4px solid #4CAF50',
            }}>
                <span style={{
                    height: 5, backgroundColor: '#4CAF50', display: 'block',
                    borderRadius: 2, position: 'absolute', zIndex: 10,
                    top: 46, left: 14, width: 25,
                    transform: 'rotate(45deg)', animation: 'icon-line-tip 0.75s',
                }} />
                <span style={{
                    height: 5, backgroundColor: '#4CAF50', display: 'block',
                    borderRadius: 2, position: 'absolute', zIndex: 10,
                    top: 38, right: 8, width: 47,
                    transform: 'rotate(-45deg)', animation: 'icon-line-long 0.75s',
                }} />
                <div style={{
                    top: -4, left: -4, zIndex: 10,
                    width: 80, height: 80, borderRadius: '50%',
                    position: 'absolute', boxSizing: 'content-box',
                    border: '4px solid rgba(76,175,80,0.5)',
                }} />
                <div style={{
                    top: 8, width: 5, left: 26, zIndex: 1,
                    height: 85, position: 'absolute',
                    transform: 'rotate(-45deg)', backgroundColor: '#fff',
                }} />
            </div>
        </div>
    );
};
