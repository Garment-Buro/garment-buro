export type PreviewDirection = 'left' | 'right';

export function getPreviewPan(viewportWidth: number, cycleWidth: number, direction: PreviewDirection = 'left') {
    if (!Number.isFinite(viewportWidth) || !Number.isFinite(cycleWidth) || viewportWidth <= 0 || cycleWidth <= 0) return null;
    return {
        // Middle copies leave identical content visible in both edge insets at wrap.
        from: direction === 'left' ? -cycleWidth : -2 * cycleWidth,
        to: direction === 'left' ? -2 * cycleWidth : -cycleWidth,
        duration: cycleWidth / 8 * 1000,
        // Keep an extra sequence available when handing off to native scrolling.
        copies: Math.ceil(viewportWidth / cycleWidth) + 3,
    };
}
