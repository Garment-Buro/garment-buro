import Image from "next/image";
import type { CSSProperties } from "react";

import type { SavedProfileItem } from "@/lib/unfinished/utils/savedItems";
import styles from "./ConstructorDraftPreview.module.css";

type ConstructorDraftPreviewProps = {
    item: SavedProfileItem;
    className?: string;
    priority?: boolean;
};

export function ConstructorDraftPreview({
    item,
    className = "",
    priority = false,
}: ConstructorDraftPreviewProps) {
    const draftState = item.draftState;

    if (!draftState) {
        return (
            <Image
                src={item.imageSrc}
                alt=""
                width={288}
                height={395}
                className={className}
                priority={priority}
            />
        );
    }

    const { activeView, canvasPixelSize, modelBounds, customization } = draftState;
    const modelImageSrc = customization.modelImages[activeView] || item.imageSrc;
    const canvasWidthCm = Math.max(1, customization.canvas.widthCm);
    const canvasHeightCm = Math.max(1, customization.canvas.heightCm);
    const safeModelWidth = Math.max(1, modelBounds.width);
    const safeModelHeight = Math.max(1, modelBounds.height);
    const canvasStyle = {
        "--draft-model-aspect": safeModelWidth / safeModelHeight,
    } as CSSProperties;
    const decorations = customization.decorations.filter((decoration) => decoration.view === activeView);

    return (
        <div
            className={`${styles.preview} ${className}`.trim()}
            data-constructor-draft-preview="true"
            data-constructor-draft-view={activeView}
        >
            <div className={styles.canvas} style={canvasStyle}>
                <span className={styles.model}>
                    <Image
                        src={modelImageSrc}
                        alt=""
                        fill
                        sizes="(max-width: 767px) 90vw, 498px"
                        className={styles.image}
                        priority={priority}
                        unoptimized
                    />
                </span>

                {decorations.map((decoration) => {
                    const left = (decoration.x - modelBounds.x) / safeModelWidth * 100;
                    const top = (decoration.y - modelBounds.y) / safeModelHeight * 100;
                    const widthPx = decoration.widthCm / canvasWidthCm * canvasPixelSize.width;
                    const heightPx = decoration.heightCm / canvasHeightCm * canvasPixelSize.height;
                    const width = widthPx / safeModelWidth * 100;
                    const height = heightPx / safeModelHeight * 100;

                    return (
                        <span
                            key={decoration.uid}
                            className={styles.decoration}
                            data-constructor-draft-decoration={decoration.variantId}
                            style={{
                                left: `${left}%`,
                                top: `${top}%`,
                                width: `${width}%`,
                                height: `${height}%`,
                                transform: `translate(-50%, -50%) rotate(${decoration.rotation}deg)`,
                            }}
                        >
                            <Image
                                src={decoration.image}
                                alt=""
                                fill
                                sizes="160px"
                                className={styles.image}
                                unoptimized
                            />
                        </span>
                    );
                })}
            </div>
        </div>
    );
}
