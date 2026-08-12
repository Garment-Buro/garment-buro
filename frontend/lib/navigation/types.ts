export type AdaptiveHeaderVariant = 'catalog' | 'constructor';

export type AdaptiveHeaderProps = {
    variant?: AdaptiveHeaderVariant;
    withBackdrop?: boolean;
    fixed?: boolean;
    topOffset?: number;
    title?: string;
    subtitle?: string;
    logoHref?: string;
    onLogoClick?: () => void;
    onMenuClick?: () => void;
    sizeLabel?: string;
    onSizeClick?: () => void;
    elevateSizeButton?: boolean;
    className?: string;
};

export type ElevatedButtonRect = {
    top: number;
    left: number;
    width: number;
};

export type CategoryMenuItem = {
    id: 'women' | 'men';
    title: string;
    subtitle: string;
    items: string[];
};

