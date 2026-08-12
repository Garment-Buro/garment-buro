import type { ImgHTMLAttributes } from 'react';

type RawMediaImageProps = Omit<ImgHTMLAttributes<HTMLImageElement>, 'alt'> & {
    alt: string;
};

/**
 * Raw image for blob/data URLs and geometry-sensitive editor canvases where
 * Next Image optimization would change the preview or positioning contract.
 */
export const RawMediaImage = ({ alt, ...props }: RawMediaImageProps) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img alt={alt} {...props} />
);
