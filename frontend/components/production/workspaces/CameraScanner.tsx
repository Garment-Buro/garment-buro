'use client';
import { useEffect, useRef, useState } from 'react';
import styles from './ProductionFlow.module.css';

export function CameraScanner({
    onRead,
    onClose,
}: {
    onRead: (value: string) => void;
    onClose: () => void;
}) {
    const video = useRef<HTMLVideoElement>(null);
    const dialog = useRef<HTMLDialogElement>(null);
    const [error, setError] = useState('');
    useEffect(() => {
        let stopped = false;
        let stream: MediaStream | undefined;
        let timer: ReturnType<typeof setTimeout> | undefined;
        dialog.current?.showModal();
        void (async () => {
            try {
                const { default: decode } = await import('jsqr');
                stream = await navigator.mediaDevices.getUserMedia({
                    video: { facingMode: { ideal: 'environment' } },
                    audio: false,
                });
                if (stopped) {
                    stream.getTracks().forEach((t) => t.stop());
                    return;
                }
                const element = video.current!;
                element.srcObject = stream;
                await element.play();
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d', {
                    willReadFrequently: true,
                })!;
                const scan = () => {
                    if (stopped) return;
                    if (element.videoWidth && element.videoHeight) {
                        canvas.width = Math.min(element.videoWidth, 800);
                        canvas.height = Math.round(
                            (element.videoHeight * canvas.width) /
                                element.videoWidth,
                        );
                        ctx.drawImage(
                            element,
                            0,
                            0,
                            canvas.width,
                            canvas.height,
                        );
                        const frame = ctx.getImageData(
                            0,
                            0,
                            canvas.width,
                            canvas.height,
                        );
                        const code = decode(
                            frame.data,
                            frame.width,
                            frame.height,
                            { inversionAttempts: 'dontInvert' },
                        );
                        if (code) {
                            onRead(code.data);
                            return;
                        }
                    }
                    timer = setTimeout(scan, 180);
                };
                scan();
            } catch {
                if (!stopped)
                    setError(
                        'Камера недоступна. Разрешите доступ в браузере или используйте поле для QR/номера заказа.',
                    );
            }
        })();
        return () => {
            stopped = true;
            clearTimeout(timer);
            stream?.getTracks().forEach((t) => t.stop());
        };
    }, [onRead]);
    return (
        <dialog
            ref={dialog}
            className={styles.sheet}
            onCancel={onClose}
            aria-label="Сканировать QR мешка"
        >
            <div className={styles.sheetBody}>
                <h2>Наведите камеру на QR</h2>
                <video
                    ref={video}
                    playsInline
                    muted
                    className={styles.cameraPreview}
                />
                {error && <p role="alert">{error}</p>}
                <button onClick={onClose}>Закрыть камеру</button>
            </div>
        </dialog>
    );
}
