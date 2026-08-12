"use client";

import { useCallback, useState } from 'react';

import { uploadMediaFile } from '@/lib/api/uploads';
import { runCatalogWrite } from '@/store/catalogWrite';

type UseMediaUploadOptions = {
    onError?: (error: unknown) => void;
};

export const useMediaUpload = ({ onError }: UseMediaUploadOptions = {}) => {
    const [isUploading, setIsUploading] = useState(false);

    const upload = useCallback(async (file: File) => {
        setIsUploading(true);
        try {
            return await runCatalogWrite(token => uploadMediaFile(file, token));
        } catch (error) {
            onError?.(error);
            return null;
        } finally {
            setIsUploading(false);
        }
    }, [onError]);

    return { isUploading, upload };
};
