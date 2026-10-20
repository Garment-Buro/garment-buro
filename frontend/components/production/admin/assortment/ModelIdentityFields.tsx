import type { Dispatch, SetStateAction } from 'react';
import type { ModelEditor } from '@/lib/production/modelEditor';
import styles from '../ProductionAdmin.module.css';
import { PiImage, PiUploadSimple } from 'react-icons/pi';
import { ReferencePicker } from './ReferencePicker';
import {
    FileUploadStatus,
    idleFileUploadStatus,
    type FileUploadStatusValue,
} from './AssortmentDialog';
export function ModelIdentityFields({
    editor,
    setEditor,
    uploading,
    uploadStatus,
    setUploadStatus,
    upload,
}: {
    editor: ModelEditor;
    setEditor: Dispatch<SetStateAction<ModelEditor | null>>;
    uploading: boolean;
    uploadStatus: FileUploadStatusValue;
    setUploadStatus: Dispatch<SetStateAction<FileUploadStatusValue>>;
    upload: (file: File) => Promise<void>;
}) {
    return (
        <fieldset className={styles.formSection}>
            <legend>Основная информация</legend>
            <div className={styles.formGrid}>
                <ReferencePicker
                    kind="model-categories"
                    required
                    activeOnly
                    value={editor.category_id ?? 0}
                    onChange={(id) =>
                        setEditor({ ...editor, category_id: id || null })
                    }
                />
                <label>
                    Название
                    <input
                        required
                        value={editor.name}
                        onChange={(event) =>
                            setEditor({
                                ...editor,
                                name: event.target.value,
                            })
                        }
                    />
                </label>
                <label>
                    Код
                    <input
                        required
                        value={editor.code}
                        placeholder="HOODIE_BASE"
                        onChange={(event) =>
                            setEditor({
                                ...editor,
                                code: event.target.value.toUpperCase(),
                            })
                        }
                    />
                </label>
                <label className={styles.fullField}>
                    Описание
                    <textarea
                        value={editor.description ?? ''}
                        onChange={(event) =>
                            setEditor({
                                ...editor,
                                description: event.target.value || null,
                            })
                        }
                    />
                </label>
                <label>
                    Базовый размер
                    <select
                        required
                        value={editor.base_size_code ?? ''}
                        onChange={(event) =>
                            setEditor({
                                ...editor,
                                base_size_code: event.target.value || null,
                            })
                        }
                    >
                        <option value="">Выберите размер</option>
                        {editor.sizes
                            .filter((size) => size.code.trim())
                            .map((size, index) => (
                                <option
                                    key={`${size.code}-${index}`}
                                    value={size.code}
                                >
                                    {size.code}
                                </option>
                            ))}
                    </select>
                    <small>Один из размеров в размерной сетке</small>
                </label>
                {([['base_weight_g', 'Вес, г']] as const).map(
                    ([field, label]) => (
                        <label key={field}>
                            {label}
                            <input
                                type="number"
                                min="0.01"
                                step="0.01"
                                value={editor[field] ?? ''}
                                onChange={(event) =>
                                    setEditor({
                                        ...editor,
                                        [field]: event.target.value || null,
                                    })
                                }
                            />
                        </label>
                    ),
                )}
                <label>
                    Имя модели на фото
                    <input
                        value={editor.fit_model_name ?? ''}
                        placeholder="Алексей"
                        onChange={(event) =>
                            setEditor({
                                ...editor,
                                fit_model_name: event.target.value || null,
                            })
                        }
                    />
                </label>
                <label>
                    Рост модели на фото, см
                    <input
                        type="number"
                        min="1"
                        step="1"
                        value={editor.fit_model_height_cm ?? ''}
                        placeholder="180"
                        onChange={(event) =>
                            setEditor({
                                ...editor,
                                fit_model_height_cm: event.target.value || null,
                            })
                        }
                    />
                </label>
                <div
                    className={`${styles.fullField} ${styles.patternFileField}`}
                >
                    <span>Таблица размеров для сайта</span>
                    <label className={styles.patternFilePicker}>
                        <input
                            type="file"
                            accept="image/jpeg,image/png,image/webp"
                            disabled={uploading}
                            onChange={async (event) => {
                                const input = event.currentTarget;
                                const file = input.files?.[0];
                                try {
                                    if (file) await upload(file);
                                } finally {
                                    input.value = '';
                                }
                            }}
                        />
                        <PiUploadSimple aria-hidden />
                        <span>
                            {editor.size_chart_url
                                ? 'Заменить изображение'
                                : 'JPEG, PNG или WebP'}
                        </span>
                    </label>
                    <FileUploadStatus value={uploadStatus} />
                </div>
                {editor.size_chart_url && (
                    <figure className={styles.sizeChartPreview}>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                            src={editor.size_chart_url}
                            alt="Загруженная таблица размеров"
                        />
                        <figcaption>
                            <PiImage aria-hidden />
                            Изображение добавлено
                            <button
                                type="button"
                                onClick={() => {
                                    setEditor({
                                        ...editor,
                                        size_chart_media_object_id: null,
                                        size_chart_url: null,
                                    });
                                    setUploadStatus(idleFileUploadStatus);
                                }}
                            >
                                Удалить
                            </button>
                        </figcaption>
                    </figure>
                )}
            </div>
        </fieldset>
    );
}
