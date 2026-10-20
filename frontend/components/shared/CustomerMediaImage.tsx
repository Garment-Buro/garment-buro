import Image, { type ImageProps } from 'next/image';
import { canOptimizePublicImage } from '@/lib/media/imagePolicy';

/** Catalog images may be optimized; account/design media keep the source's private response. */
export function CustomerMediaImage(props: ImageProps) {
    const direct = typeof props.src === 'string' && !canOptimizePublicImage(props.src);
    return <Image {...props} unoptimized={direct || props.unoptimized} referrerPolicy={direct ? 'no-referrer' : props.referrerPolicy} />;
}
