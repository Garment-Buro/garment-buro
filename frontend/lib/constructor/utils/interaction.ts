export type ScaleLimitsInput = {
    isCustom?: boolean;
    minScale: number;
    maxScale: number;
};

export const getCustomDecorationScaleLimits = ({ isCustom, minScale, maxScale }: ScaleLimitsInput) => {
    const min = isCustom ? Math.max(1, minScale) : minScale;
    return { min, max: Math.max(min, maxScale) };
};

export const canPanStage = (stageScale: number, fittedScale: number, epsilon = 0.01) => (
    stageScale > fittedScale + epsilon
);

export const getVisibleCanvasHeight = (containerHeight: number, bottomInset: number) => (
    Math.max(1, containerHeight - Math.max(0, bottomInset))
);

export type StagePanBoundsInput = {
    containerWidth: number;
    containerHeight: number;
    bottomInset: number;
    scale: number;
    bounds: { x: number; y: number; width: number; height: number };
};

export const getStagePanBounds = ({ containerWidth, containerHeight, bottomInset, scale, bounds }: StagePanBoundsInput) => {
    const centerX = containerWidth / 2;
    const centerY = getVisibleCanvasHeight(containerHeight, bottomInset) / 2;
    return {
        minX: centerX - (bounds.x + bounds.width) * scale,
        maxX: centerX - bounds.x * scale,
        minY: centerY - (bounds.y + bounds.height) * scale,
        maxY: centerY - bounds.y * scale,
    };
};

export const shouldDeferHardwareSelection = (selectedHardwareUid: string | null, targetHardwareUid: string) => (
    Boolean(selectedHardwareUid && selectedHardwareUid !== targetHardwareUid)
);

type DecorationDropPoint = { x: number; y: number };
type DecorationDropInput = {
    centerPoint: DecorationDropPoint;
    existingItems: DecorationDropPoint[];
    canvasSize?: number;
    minSpacing?: number;
};

const DECORATION_DROP_OFFSETS: DecorationDropPoint[] = [
    { x: 80, y: 0 }, { x: -80, y: 0 }, { x: 0, y: 80 }, { x: 0, y: -80 },
    { x: 58, y: 58 }, { x: -58, y: 58 }, { x: 58, y: -58 }, { x: -58, y: -58 },
];

const clampDropCoordinate = (value: number, canvasSize: number) => Math.min(Math.max(value, 0), canvasSize);

export const getNextDecorationDropPosition = ({
    centerPoint,
    existingItems,
    canvasSize = 1000,
    minSpacing = 72,
}: DecorationDropInput): DecorationDropPoint => {
    const center = {
        x: clampDropCoordinate(centerPoint.x, canvasSize),
        y: clampDropCoordinate(centerPoint.y, canvasSize),
    };
    const isOccupied = (point: DecorationDropPoint) => existingItems.some(
        (item) => Math.hypot(item.x - point.x, item.y - point.y) < minSpacing,
    );
    if (!isOccupied(center)) return center;

    for (let ring = 1; ring <= 6; ring += 1) {
        for (const offset of DECORATION_DROP_OFFSETS) {
            const candidate = {
                x: clampDropCoordinate(center.x + offset.x * ring, canvasSize),
                y: clampDropCoordinate(center.y + offset.y * ring, canvasSize),
            };
            if (!isOccupied(candidate)) return candidate;
        }
    }
    return center;
};

export type PanelSwipeInput = {
    isExpanded: boolean;
    deltaX: number;
    deltaY: number;
    threshold?: number;
};

export const getPanelSwipeAction = ({
    isExpanded,
    deltaX,
    deltaY,
    threshold = 45,
}: PanelSwipeInput): "expand" | "collapse" | "ignore" => {
    if (Math.abs(deltaY) <= threshold || Math.abs(deltaY) <= Math.abs(deltaX)) return "ignore";
    if (!isExpanded && deltaY < 0) return "expand";
    if (isExpanded && deltaY > 0) return "collapse";
    return "ignore";
};
