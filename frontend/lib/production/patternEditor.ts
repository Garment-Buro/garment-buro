import type { Pattern } from './assortmentTypes.ts';
import type {
    PatternContext,
    PatternModel,
    PatternSize,
} from './patternDirectory.ts';
import { sleeveVariants } from './patternDirectory.ts';
import { compactDecimal } from './numbers.ts';

export type PatternPoint = {
    width?: string;
    length?: string;
    variant?: Pattern['sleeve_variant'];
};
export type PatternForm = Omit<Pattern, 'id' | 'version' | 'grid_key'> & {
    id?: number;
    version?: number;
    filename?: string;
};
export const variantLabel = {
    standard: 'Стандартный рукав',
    height: 'Рукав по росту',
};
export const variantShortLabel = { standard: 'Стандарт', height: 'По росту' };
export const generatedPatternCode = (
    model: PatternModel,
    size: PatternSize,
    width: string,
    length: string,
    variant: Pattern['sleeve_variant'],
) => {
    const part = (value: string) => compactDecimal(value).replace('.', '_');
    const suffix = `-${size.code}-${part(width)}X${part(length)}-${variant === 'height' ? 'H' : 'S'}`;
    return `${`PAT-${model.code}`.slice(0, 64 - suffix.length)}${suffix}`;
};
export const patternForm = (
    context: PatternContext,
    point: PatternPoint = {},
): PatternForm => {
    if (!context.size) throw new Error('Выберите размер лекала.');
    const pattern = context.pattern;
    if (pattern)
        return {
            ...pattern,
            width_cm: compactDecimal(pattern.width_cm),
            length_cm: compactDecimal(pattern.length_cm),
        };
    const width = point.width ?? context.size.min_width_cm ?? '',
        length = point.length ?? context.size.min_length_cm ?? '',
        variant = point.variant ?? sleeveVariants(context.size)[0];
    const code =
        width && length
            ? generatedPatternCode(
                  context.model,
                  context.size,
                  width,
                  length,
                  variant,
              )
            : '';
    return {
        garment_model_id: context.model.id,
        garment_size_id: context.size.id,
        code,
        name: code,
        media_object_id: 0,
        width_cm: width,
        length_cm: length,
        sleeve_variant: variant,
        is_active: true,
    };
};
export const cmCents = (value: string) => {
    const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(value);
    return match
        ? Number(match[1]) * 100 + Number((match[2] ?? '').padEnd(2, '0'))
        : NaN;
};
export const validMeasurement = (
    value: string,
    minimum: string | null,
    maximum: string | null,
) => {
    if (minimum === null || maximum === null) return false;
    const v = cmCents(value),
        min = cmCents(minimum),
        max = cmCents(maximum);
    return (
        Number.isSafeInteger(v) && v >= min && v <= max && (v - min) % 200 === 0
    );
};
export const validPatternGeometry = (editor: PatternForm, size: PatternSize) =>
    sleeveVariants(size).includes(editor.sleeve_variant) &&
    validMeasurement(editor.width_cm, size.min_width_cm, size.max_width_cm) &&
    validMeasurement(editor.length_cm, size.min_length_cm, size.max_length_cm);
export const changePatternCode = (editor: PatternForm, code: string) => ({
    ...editor,
    code,
    name: editor.name === editor.code ? code : editor.name,
});
export const changePatternGeometry = (
    editor: PatternForm,
    context: PatternContext,
    changes: Partial<
        Pick<PatternForm, 'width_cm' | 'length_cm' | 'sleeve_variant'>
    >,
) => {
    const next = { ...editor, ...changes };
    if (
        !next.id &&
        context.size &&
        Number.isFinite(cmCents(next.width_cm)) &&
        Number.isFinite(cmCents(next.length_cm))
    )
        return changePatternCode(
            next,
            generatedPatternCode(
                context.model,
                context.size,
                next.width_cm,
                next.length_cm,
                next.sleeve_variant,
            ),
        );
    return next;
};
export const patternWrite = (editor: PatternForm) => ({
    code: editor.code,
    name: editor.name,
    garment_model_id: editor.garment_model_id,
    garment_size_id: editor.garment_size_id,
    media_object_id: editor.media_object_id,
    width_cm: editor.width_cm,
    length_cm: editor.length_cm,
    sleeve_variant: editor.sleeve_variant,
    is_active: editor.is_active,
    ...(editor.id ? { expected_version: editor.version } : {}),
});
