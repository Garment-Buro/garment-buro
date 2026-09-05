import type { TextDecoration, UploadedImage } from '../types.ts';

export const TEXT_FONTS = [
    { id: 'manrope', label: 'Manrope', family: 'var(--font-manrope), sans-serif', variable: '--font-manrope', fallback: 'sans-serif', weight: 700 },
    { id: 'inter', label: 'Inter', family: 'var(--font-inter), sans-serif', variable: '--font-inter', fallback: 'sans-serif', weight: 800 },
    { id: 'mono', label: 'Моноширинный', family: 'monospace', variable: '', fallback: 'monospace', weight: 700 },
    { id: 'serif', label: 'С засечками', family: 'Georgia, serif', variable: '', fallback: 'Georgia, serif', weight: 700 },
] as const;

export const DEFAULT_TEXT_DECORATION: TextDecoration = {
    content: '', fontId: 'manrope', fontSize: 40, color: '#181818',
};

export const normalizeTextDecoration = (value: TextDecoration): TextDecoration => ({
    content: value.content.replace(/\r\n?/g, '\n').slice(0, 200).split('\n').slice(0, 6).join('\n').trim(),
    fontId: TEXT_FONTS.some((font) => font.id === value.fontId) ? value.fontId : 'manrope',
    fontSize: Math.min(120, Math.max(12, Math.round(Number(value.fontSize) || 40))),
    color: /^#[0-9a-f]{6}$/i.test(value.color) ? value.color : '#181818',
});

// The transparent preview travels through the existing decoration pipeline;
// editable text parameters are saved beside it in the customization snapshot.
export const renderTextDecoration = async (input: TextDecoration): Promise<UploadedImage & { text: TextDecoration }> => {
    const text = normalizeTextDecoration(input);
    if (!text.content) throw new Error('Введите текст надписи.');
    const font = TEXT_FONTS.find((entry) => entry.id === text.fontId)!;
    const family = font.variable
        ? getComputedStyle(document.body).getPropertyValue(font.variable).trim() || font.fallback
        : font.fallback;
    const fontStyle = `${font.weight} ${text.fontSize}px ${family}`;
    await document.fonts.load(fontStyle, text.content);
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    if (!context) throw new Error('Не удалось создать надпись. Попробуйте ещё раз.');
    context.font = fontStyle;
    const lines = text.content.split('\n');
    const padding = Math.ceil(text.fontSize * 0.25);
    const width = Math.ceil(Math.max(...lines.map((line) => context.measureText(line).width))) + padding * 2;
    const lineHeight = text.fontSize * 1.3;
    const height = Math.ceil(lineHeight * lines.length) + padding * 2;
    // Bound both raster dimensions and memory, including long pasted strings.
    const density = Math.min(4, 4096 / Math.max(width, height));
    canvas.width = Math.ceil(width * density);
    canvas.height = Math.ceil(height * density);
    context.scale(density, density);
    context.font = fontStyle;
    context.fillStyle = text.color;
    context.textAlign = 'center';
    context.textBaseline = 'alphabetic';
    lines.forEach((line, index) => context.fillText(line, width / 2, padding + text.fontSize + lineHeight * index));
    return { src: canvas.toDataURL('image/png'), width, height, text };
};
