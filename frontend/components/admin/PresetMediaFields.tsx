import type { PresetEditor } from '@/lib/production/presetEditor';
import { setPresetField, type PresetFieldsProps } from './presetFields';
import { ProductEditorMedia } from './ProductEditorMedia';
import styles from '@/components/production/admin/ProductionAdmin.module.css';
const galleries = [
    ['gallery_images', 'Дополнительные фото'],
    ['desktop_card_images', 'Фото для карточки на компьютере'],
    ['desktop_slider_images', 'Галерея на компьютере'],
    ['mobile_slider_images', 'Галерея карточки на телефоне'],
    ['mobile_product_slider_images', 'Галерея товара на телефоне'],
] as const;

export function PresetMediaFields({
    editor,
    setEditor,
    disabled,
    upload,
}: PresetFieldsProps & { upload: (files: File[]) => Promise<string[]> }) {
    const set = <K extends keyof PresetEditor>(
        key: K,
        value: PresetEditor[K],
    ) => setPresetField(setEditor, key, value);
    return (
        <fieldset className={styles.formSection} disabled={disabled}>
            <legend>Изображения</legend>
            <ProductEditorMedia
                label="Основное изображение"
                value={editor.image_left}
                upload={upload}
                onChange={(value) => set('image_left', value)}
            />
            <ProductEditorMedia
                label="Фото с обратной стороны"
                value={editor.image_right}
                upload={upload}
                onChange={(value) => set('image_right', value)}
            />
            <ProductEditorMedia
                label="Обложка карточки"
                value={editor.mobile_card_image}
                upload={upload}
                onChange={(value) => set('mobile_card_image', value)}
            />
            <details>
                <summary>Дополнительные галереи</summary>
                {galleries.map(([key, label]) => (
                    <ProductEditorMedia
                        key={key}
                        label={label}
                        value={editor[key]}
                        multiple
                        upload={upload}
                        onChange={(value) => set(key, value)}
                    />
                ))}
            </details>
        </fieldset>
    );
}
