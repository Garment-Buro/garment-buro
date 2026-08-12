export const runAfterInitialPaint = (callback: () => void) => {
    let didRun = false;
    let idleId: number | undefined;
    const run = () => {
        if (didRun) return;
        didRun = true;
        callback();
    };
    const timeoutId = window.setTimeout(run, 700);
    if ('requestIdleCallback' in window) idleId = window.requestIdleCallback(run, { timeout: 2000 });

    return () => {
        window.clearTimeout(timeoutId);
        if (idleId !== undefined && 'cancelIdleCallback' in window) window.cancelIdleCallback(idleId);
    };
};

export const loadScriptOnce = (id: string, src: string) => new Promise<void>((resolve, reject) => {
    const existing = document.getElementById(id) as HTMLScriptElement | null;
    if (existing?.dataset.loaded === 'true') return resolve();

    const script = existing || document.createElement('script');
    const cleanup = () => {
        script.removeEventListener('load', onLoad);
        script.removeEventListener('error', onError);
    };
    const onLoad = () => {
        script.dataset.loaded = 'true';
        cleanup();
        resolve();
    };
    const onError = () => {
        cleanup();
        reject(new Error(`Failed to load ${src}`));
    };

    script.addEventListener('load', onLoad);
    script.addEventListener('error', onError);
    if (!existing) {
        script.id = id;
        script.src = src;
        script.async = true;
        script.defer = true;
        document.head.appendChild(script);
    }
});
