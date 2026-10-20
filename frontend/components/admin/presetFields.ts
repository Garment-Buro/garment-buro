import type { Dispatch, SetStateAction } from 'react';
import type { PresetEditor } from '@/lib/production/presetEditor';

export interface PresetFieldsProps {
    editor: PresetEditor;
    setEditor: Dispatch<SetStateAction<PresetEditor | null>>;
    disabled: boolean;
}
export const setPresetField = <K extends keyof PresetEditor>(
    setEditor: PresetFieldsProps['setEditor'],
    key: K,
    value: PresetEditor[K],
) => setEditor((current) => (current ? { ...current, [key]: value } : current));
