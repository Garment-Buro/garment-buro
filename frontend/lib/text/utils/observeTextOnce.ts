/** Observe only text that actually requests a reveal on entering the viewport. */
export function observeTextOnce(element: Element, onVisible: () => void): () => void {
    if (typeof IntersectionObserver === 'undefined') {
        onVisible();
        return () => {};
    }

    let active = true;
    const observer = new IntersectionObserver(entries => {
        if (!active || !entries.some(entry => entry.target === element && entry.isIntersecting)) return;
        active = false;
        observer.disconnect();
        onVisible();
    });
    observer.observe(element);
    return () => {
        active = false;
        observer.disconnect();
    };
}
