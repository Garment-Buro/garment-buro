"use client";

import Image from "next/image";
import { useId, useLayoutEffect, useRef } from "react";

import { useInlineAutoplayVideo } from "@/hooks/media/useInlineAutoplayVideo";

import styles from "./CartActionBarV2.module.css";

type CartActionBarV2CollapsedProps = {
    isAuthenticated: boolean;
    shifted: boolean;
    totalQuantity: number;
    onLogin: () => void;
    onOpen: () => void;
};

const getLiquidTargetX = (width: number, shifted: boolean) => (
    shifted ? Math.min(width * 0.42, 160) : width * 0.785
);

const createLiquidPath = (
    width: number,
    height: number,
    targetX: number,
    deformation: number,
) => {
    const radius = height / 2;
    const neckHalf = Math.min(22, height * 0.48);
    const center = Math.max(
        radius + neckHalf + 2,
        Math.min(width - radius - neckHalf - 2, targetX),
    );
    const depth = height * (0.12 + deformation * 0.1);
    const innerControl = neckHalf * 0.34;
    const outerControl = neckHalf * 0.78;

    return [
        `M ${radius} 0`,
        `H ${center - neckHalf}`,
        `C ${center - outerControl} 0, ${center - innerControl} ${depth}, ${center} ${depth}`,
        `C ${center + innerControl} ${depth}, ${center + outerControl} 0, ${center + neckHalf} 0`,
        `H ${width - radius}`,
        `A ${radius} ${radius} 0 0 1 ${width} ${radius}`,
        `A ${radius} ${radius} 0 0 1 ${width - radius} ${height}`,
        `H ${center + neckHalf}`,
        `C ${center + outerControl} ${height}, ${center + innerControl} ${height - depth}, ${center} ${height - depth}`,
        `C ${center - innerControl} ${height - depth}, ${center - outerControl} ${height}, ${center - neckHalf} ${height}`,
        `H ${radius}`,
        `A ${radius} ${radius} 0 0 1 0 ${radius}`,
        `A ${radius} ${radius} 0 0 1 ${radius} 0`,
        "Z",
    ].join(" ");
};

function CartV2Logo() {
    const {
        videoRef,
        hasPlayingFrame,
        tryPlay,
        handlePlaying,
        handleError,
    } = useInlineAutoplayVideo();

    return (
        <span className={styles.logo} aria-hidden="true">
            <Image
                src="/pwa-icon-source.png"
                alt=""
                fill
                sizes="35px"
                className={styles.logoFallback}
            />
            <video
                ref={videoRef}
                src="/logo_anim_cart.mp4"
                autoPlay
                loop
                muted
                playsInline
                controls={false}
                disablePictureInPicture
                controlsList="nodownload nofullscreen noremoteplayback"
                preload="auto"
                onCanPlay={tryPlay}
                onLoadedData={tryPlay}
                onPlaying={handlePlaying}
                onError={handleError}
                className={styles.logoVideo}
                style={{ opacity: hasPlayingFrame ? 1 : 0 }}
            />
        </span>
    );
}

export function CartActionBarV2Collapsed({
    isAuthenticated,
    shifted,
    totalQuantity,
    onLogin,
    onOpen,
}: CartActionBarV2CollapsedProps) {
    const rootRef = useRef<HTMLDivElement>(null);
    const clipPathRef = useRef<SVGPathElement>(null);
    const outlinePathRef = useRef<SVGPathElement>(null);
    const currentXRef = useRef(0);
    const velocityXRef = useRef(0);
    const deformationRef = useRef(0);
    const dimensionsRef = useRef({ width: 0, height: 45 });
    const clipId = `cart-v2-${useId().replaceAll(":", "")}`;

    useLayoutEffect(() => {
        const root = rootRef.current;
        const clipPath = clipPathRef.current;
        const outlinePath = outlinePathRef.current;
        if (!root || !clipPath || !outlinePath) return;

        let animationFrame = 0;

        const renderPath = () => {
            const { width, height } = dimensionsRef.current;
            const path = createLiquidPath(
                width,
                height,
                currentXRef.current,
                deformationRef.current,
            );
            clipPath.setAttribute("d", path);
            outlinePath.setAttribute("d", path);
        };

        const draw = () => {
            animationFrame = 0;

            const { width } = dimensionsRef.current;
            const targetX = getLiquidTargetX(width, shifted);
            const distance = targetX - currentXRef.current;
            const deformationTarget = Math.min(1, Math.abs(distance) / Math.max(1, width * 0.12));

            velocityXRef.current += distance * 0.021;
            velocityXRef.current *= 0.76;
            currentXRef.current += velocityXRef.current;
            deformationRef.current += (
                deformationTarget - deformationRef.current
            ) * (deformationTarget > deformationRef.current ? 0.12 : 0.075);

            const isSettled = (
                Math.abs(distance) < 0.08
                && Math.abs(velocityXRef.current) < 0.08
                && deformationRef.current < 0.002
            );

            if (isSettled) {
                currentXRef.current = targetX;
                velocityXRef.current = 0;
                deformationRef.current = 0;
                renderPath();
                return;
            }

            renderPath();
            animationFrame = window.requestAnimationFrame(draw);
        };

        const scheduleDraw = () => {
            if (animationFrame) return;
            animationFrame = window.requestAnimationFrame(draw);
        };

        const syncDimensions = () => {
            const rect = root.getBoundingClientRect();
            dimensionsRef.current = {
                width: rect.width,
                height: rect.height,
            };

            const svg = root.querySelector("svg");
            svg?.setAttribute("viewBox", `0 0 ${rect.width} ${rect.height}`);

            if (!currentXRef.current) {
                currentXRef.current = getLiquidTargetX(rect.width, shifted);
            }
            scheduleDraw();
        };

        const resizeObserver = new ResizeObserver(syncDimensions);
        resizeObserver.observe(root);
        syncDimensions();

        return () => {
            resizeObserver.disconnect();
            window.cancelAnimationFrame(animationFrame);
        };
    }, [shifted]);

    return (
        <div
            ref={rootRef}
            className={styles.root}
            data-cart-v2-shifted={shifted}
        >
            <svg className={styles.liquidSvg} aria-hidden="true">
                <defs>
                    <clipPath id={clipId} clipPathUnits="userSpaceOnUse">
                        <path ref={clipPathRef} />
                    </clipPath>
                </defs>
                <image
                    href="/cartv2_bg.png"
                    width="100%"
                    height="100%"
                    preserveAspectRatio="xMidYMid slice"
                    clipPath={`url(#${clipId})`}
                />
                <path
                    ref={outlinePathRef}
                    className={styles.liquidOutline}
                    vectorEffect="non-scaling-stroke"
                />
            </svg>

            <div className={styles.content}>
                <div className={styles.brand}>
                    <CartV2Logo />
                    <span className={styles.brandName}>Garment Buro</span>
                </div>

                <button
                    type="button"
                    className={styles.login}
                    onClick={onLogin}
                >
                    {isAuthenticated ? "Личный кабинет" : "Войти в ЛК"}
                </button>

                <button
                    type="button"
                    className={styles.cart}
                    onClick={onOpen}
                >
                    Корзина ({totalQuantity})
                </button>

                <button
                    type="button"
                    className={styles.combined}
                    onClick={onLogin}
                >
                    Узнать о нас больше
                </button>
            </div>
        </div>
    );
}
