type RotateModelIconProps = {
    direction: "left" | "right";
};

export function RotateModelIcon({ direction }: RotateModelIconProps) {
    const isLeft = direction === "left";

    return (
        <svg
            width="27"
            height="18"
            viewBox="0 0 27 18"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="relative z-[1] h-[18px] w-[27px] shrink-0 text-[#969696]"
            shapeRendering="geometricPrecision"
            aria-hidden="true"
        >
            <path
                d={isLeft
                    ? "M9.73 14.19C6.89 13.71 4.45 12.68 2.88 11.31C1.3 9.94 0.69 8.31 1.15 6.72C1.61 5.12 3.11 3.67 5.38 2.62C7.65 1.57 10.54 1 13.53 1C16.51 1 19.4 1.58 21.66 2.64C23.93 3.69 25.41 5.15 25.86 6.74C26.31 8.34 25.68 9.97 24.1 11.34C22.51 12.7 20.07 13.72 17.22 14.2"
                    : "M17.27 14.19C20.12 13.71 22.55 12.68 24.12 11.31C25.7 9.94 26.31 8.31 25.85 6.72C25.4 5.12 23.89 3.67 21.62 2.62C19.35 1.57 16.46 1 13.48 1C10.49 1 7.6 1.58 5.34 2.64C3.08 3.69 1.59 5.15 1.14 6.74C0.7 8.34 1.32 9.97 2.91 11.34C4.49 12.7 6.93 13.72 9.78 14.2"}
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                vectorEffect="non-scaling-stroke"
            />
            <path
                d={isLeft ? "M7.5 10L11 13.85L7 17" : "M19.5 10L16 13.85L20 17"}
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
            />
        </svg>
    );
}
