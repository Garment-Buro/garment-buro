export function getPreviewPan(viewportWidth: number, contentWidth: number): { distance: number; duration: number } | null {
    if (!Number.isFinite(viewportWidth) || !Number.isFinite(contentWidth) || viewportWidth <= 0) return null;
    const distance = contentWidth - viewportWidth;
    // Tiny overflows should not produce a distracting short oscillation.
    return distance > 8 ? { distance, duration: distance / 8 * 1000 } : null;
}
