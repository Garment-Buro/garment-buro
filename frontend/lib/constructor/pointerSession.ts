type PointerHandlers = {
    onMove: (event: PointerEvent) => void;
    onEnd?: (event: PointerEvent) => void;
    onCancel?: () => void;
};

/** One editor owns one active pointer gesture; cancellation never completes a tap. */
export function createPointerSession(target: EventTarget, visibility: EventTarget & { hidden: boolean }) {
    let stop: (() => void) | null = null;
    let disposed = false;
    const cancel = () => stop?.();

    return {
        cancel,
        start(pointerId: number, handlers: PointerHandlers) {
            cancel();
            if (disposed) return;
            let active = true;
            const cleanup = () => {
                if (!active) return;
                active = false;
                target.removeEventListener('pointermove', move);
                target.removeEventListener('pointerup', end);
                target.removeEventListener('pointercancel', cancelled);
                target.removeEventListener('blur', cancelled);
                visibility.removeEventListener('visibilitychange', hidden);
                stop = null;
            };
            const abort = () => {
                if (!active) return;
                cleanup();
                handlers.onCancel?.();
            };
            const move = (event: Event) => {
                if (active && (event as PointerEvent).pointerId === pointerId) handlers.onMove(event as PointerEvent);
            };
            const end = (event: Event) => {
                if (!active || (event as PointerEvent).pointerId !== pointerId) return;
                cleanup();
                handlers.onEnd?.(event as PointerEvent);
            };
            const cancelled = (event: Event) => {
                if (event.type === 'blur' || (event as PointerEvent).pointerId === pointerId) abort();
            };
            const hidden = () => { if (visibility.hidden) abort(); };
            stop = abort;
            target.addEventListener('pointermove', move);
            target.addEventListener('pointerup', end);
            target.addEventListener('pointercancel', cancelled);
            target.addEventListener('blur', cancelled);
            visibility.addEventListener('visibilitychange', hidden);
            if (visibility.hidden) abort();
        },
        dispose() {
            disposed = true;
            cancel();
        },
    };
}
