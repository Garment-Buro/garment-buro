import { useRef, useState } from 'react';
import { RawMediaImage } from '@/components/shared/RawMediaImage';
import { parseMediaCsv } from '@/lib/media/utils/mediaUrl';

/** The editor owns one operation for the entire upload batch. */
export function ProductEditorMedia({
    label,
    value,
    multiple = false,
    onChange,
    upload,
    disabled = false,
}: {
    label: string;
    value: string | null;
    multiple?: boolean;
    onChange: (value: string | null) => void;
    upload: (files: File[]) => Promise<string[]>;
    disabled?: boolean;
}) {
    const lock = useRef(false);
    const [status, setStatus] = useState(''),
        [busy, setBusy] = useState(false),
        [failed, setFailed] = useState(false);
    const images = parseMediaCsv(value);
    return (
        <div>
            <label>
                {label}
                <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    multiple={multiple}
                    disabled={disabled || busy}
                    onChange={async (event) => {
                        const input = event.currentTarget;
                        const files = Array.from(input.files ?? []);
                        if (!files.length || lock.current) return;
                        lock.current = true;
                        setBusy(true);
                        setFailed(false);
                        setStatus('Загружаем…');
                        try {
                            // Publish once after every file is confirmed; failure never silently drops an existing image.
                            const urls = await upload(files);
                            onChange(
                                (multiple
                                    ? [...images, ...urls]
                                    : urls.slice(0, 1)
                                ).join(',') || null,
                            );
                            setStatus('Изображения загружены');
                        } catch (reason) {
                            setFailed(true);
                            setStatus(
                                reason instanceof Error
                                    ? reason.message
                                    : 'Не удалось загрузить изображение.',
                            );
                        } finally {
                            lock.current = false;
                            input.value = '';
                            setBusy(false);
                        }
                    }}
                />
            </label>
            {status && (
                <p role={failed ? 'alert' : 'status'} aria-live="polite">
                    {status}
                </p>
            )}
            <div className="flex flex-wrap gap-3">
                {images.map((url, index) => (
                    <div key={`${url}-${index}`}>
                        <RawMediaImage
                            src={url}
                            alt={label}
                            width={80}
                            height={80}
                            className="object-contain"
                        />
                        <button
                            type="button"
                            disabled={disabled || busy}
                            onClick={() =>
                                onChange(
                                    images
                                        .filter((_, i) => i !== index)
                                        .join(',') || null,
                                )
                            }
                            aria-label={`Убрать ${label.toLowerCase()} ${index + 1}`}
                        >
                            Убрать
                        </button>
                    </div>
                ))}
            </div>
        </div>
    );
}
