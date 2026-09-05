export type SplashPlaybackResult = 'playing' | 'blocked' | 'error' | 'interrupted';

/** Keep play() in the caller's gesture; do not defer it to an effect or timer. */
export async function playSplashVideo(video: HTMLVideoElement): Promise<SplashPlaybackResult> {
    video.muted = true;
    video.defaultMuted = true;
    video.autoplay = true;
    video.playsInline = true;
    video.setAttribute('muted', '');
    video.setAttribute('autoplay', '');
    video.setAttribute('playsinline', '');
    video.setAttribute('webkit-playsinline', '');
    video.removeAttribute('controls');
    try {
        await video.play();
        return 'playing';
    } catch (error) {
        const name = error instanceof Error ? error.name : '';
        if (name === 'AbortError') return 'interrupted';
        return name === 'NotAllowedError' ? 'blocked' : 'error';
    }
}
