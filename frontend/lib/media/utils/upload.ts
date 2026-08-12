export const ALLOWED_IMAGE_MIME_TYPES = [
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/avif',
    'image/gif',
] as const;

export const ALLOWED_VIDEO_MIME_TYPES = [
    'video/mp4',
    'video/webm',
    'video/quicktime',
] as const;

export const IMAGE_FILE_ACCEPT = ALLOWED_IMAGE_MIME_TYPES.join(',');
export const MEDIA_FILE_ACCEPT = [...ALLOWED_IMAGE_MIME_TYPES, ...ALLOWED_VIDEO_MIME_TYPES].join(',');

const allowedMediaTypes = new Set<string>([
    ...ALLOWED_IMAGE_MIME_TYPES,
    ...ALLOWED_VIDEO_MIME_TYPES,
]);

export const isSupportedImageFile = (file: Pick<File, 'type'>) => (
    ALLOWED_IMAGE_MIME_TYPES.includes(file.type as typeof ALLOWED_IMAGE_MIME_TYPES[number])
);

export const assertSupportedMediaFile = (file: Pick<File, 'type'>) => {
    if (!allowedMediaTypes.has(file.type)) {
        throw new Error('Неподдерживаемый формат файла. SVG и другие активные форматы загружать нельзя.');
    }
};
