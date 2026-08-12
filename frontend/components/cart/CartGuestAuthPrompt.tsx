import { useInlineAutoplayVideo } from "@/hooks/media/useInlineAutoplayVideo";

export const CartGuestAuthPrompt = ({ onLogin }: { onLogin: () => void }) => {
    const { videoRef, hasPlayingFrame, tryPlay, handlePlaying, handleError } = useInlineAutoplayVideo();

    return (
        <div
        className="cart-action-bar-guest-auth flex w-full items-center rounded-[14px]"
        style={{
            minHeight: '90px', height: '90px', maxHeight: '90px', boxSizing: 'border-box', overflow: 'hidden',
            marginTop: 7, padding: '13px 11px', background: 'rgb(255 255 255)', border: '1px solid rgba(255, 255, 255, 0.3)',
            boxShadow: '0 0 16px 3px rgba(255, 255, 255, 0.82), 0 8px 32px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(255, 255, 255, 0.5) inset',
            backdropFilter: 'blur(12px) saturate(160%)', WebkitBackdropFilter: 'blur(12px) saturate(160%)',
        }}
    >
        <div className="flex min-w-0 items-center gap-[12px]">
            <div className="relative h-[64px] w-[64px] shrink-0 overflow-hidden rounded-full">
                <video
                    ref={videoRef}
                    src="/logo_anim.mp4"
                    autoPlay
                    loop
                    muted
                    playsInline
                    controls={false}
                    disablePictureInPicture
                    controlsList="nodownload nofullscreen noremoteplayback"
                    preload="auto"
                    aria-hidden="true"
                    onCanPlayThrough={tryPlay}
                    onCanPlay={tryPlay}
                    onLoadedMetadata={tryPlay}
                    onLoadedData={tryPlay}
                    onPlaying={handlePlaying}
                    onError={handleError}
                    onStalled={tryPlay}
                    onWaiting={tryPlay}
                    className="cart-action-bar-guest-logo-video absolute inset-0 h-full w-full object-cover mix-blend-multiply"
                    style={{
                        pointerEvents: "none",
                        opacity: hasPlayingFrame ? 1 : 0,
                        transition: "opacity 120ms ease-out",
                    }}
                />
            </div>
            <div className="flex min-w-0 flex-col gap-[0px]">
                <span className="whitespace-nowrap font-manrope text-[18px] font-semibold leading-normal text-[#646464]">Garment Buro</span>
                <span className="font-manrope text-[10px] font-normal leading-normal text-[#AAA]">my collection</span>
            </div>
        </div>
        <div className="ml-auto flex shrink-0 justify-end" style={{ paddingLeft: 'clamp(75px, 20.27vw, 130px)' }}>
            <button type="button" className="shrink-0 whitespace-nowrap border-0 bg-transparent py-[12px] pl-0 pr-[27px] font-manrope text-[10px] font-normal leading-normal text-[#AAA]" onClick={onLogin}>Войти</button>
        </div>
        </div>
    );
};
