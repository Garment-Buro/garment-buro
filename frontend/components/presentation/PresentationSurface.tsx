"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

import { PresentationRoadmap } from "./PresentationRoadmap";
import styles from "./PresentationSurface.module.css";

type PresentationSurfaceProps = {
    isOverlay?: boolean;
};

export function PresentationSurface({ isOverlay = false }: PresentationSurfaceProps) {
    const router = useRouter();
    const dialogRef = useRef<HTMLElement>(null);
    const heroRef = useRef<HTMLDivElement>(null);

    const close = () => {
        if (isOverlay) {
            router.back();
            return;
        }

        router.push("/");
    };

    useEffect(() => {
        const html = document.documentElement;
        const body = document.body;
        const scrollY = window.scrollY;
        const previousHtmlOverflow = html.style.overflow;
        const previousBodyOverflow = body.style.overflow;
        const previousBodyPosition = body.style.position;
        const previousBodyTop = body.style.top;
        const previousBodyWidth = body.style.width;

        html.style.overflow = "hidden";
        body.style.overflow = "hidden";
        body.style.position = "fixed";
        body.style.top = `-${scrollY}px`;
        body.style.width = "100%";
        dialogRef.current?.focus();

        return () => {
            html.style.overflow = previousHtmlOverflow;
            body.style.overflow = previousBodyOverflow;
            body.style.position = previousBodyPosition;
            body.style.top = previousBodyTop;
            body.style.width = previousBodyWidth;
            window.scrollTo(0, scrollY);
        };
    }, []);

    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") close();
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    });

    useEffect(() => {
        const sheet = dialogRef.current;
        const hero = heroRef.current;

        if (!sheet || !hero) return;

        let animationFrame = 0;

        const updateScrollState = () => {
            animationFrame = 0;

            const viewportProgress = Math.min(1, Math.max(0, (window.innerWidth - 370) / 190));
            const heroPeekHeight = 97 + (25 * viewportProgress);
            const pinThreshold = Math.max(0, hero.offsetHeight - heroPeekHeight);

            sheet.style.setProperty("--presentation-hero-peek", `${heroPeekHeight}px`);
            hero.dataset.heroPeekPinned = String(sheet.scrollTop >= pinThreshold);
        };

        const scheduleUpdate = () => {
            if (animationFrame) return;
            animationFrame = window.requestAnimationFrame(updateScrollState);
        };

        updateScrollState();
        sheet.addEventListener("scroll", scheduleUpdate, { passive: true });
        window.addEventListener("resize", scheduleUpdate);

        return () => {
            sheet.removeEventListener("scroll", scheduleUpdate);
            window.removeEventListener("resize", scheduleUpdate);
            window.cancelAnimationFrame(animationFrame);
        };
    }, []);

    return (
        <div className={styles.overlayRoot} data-presentation-overlay>
            <button
                type="button"
                className={styles.backdrop}
                onClick={close}
                aria-label="Закрыть презентацию"
            />

            <section
                ref={dialogRef}
                className={styles.sheet}
                role="dialog"
                aria-modal="true"
                aria-label="Презентация Garment Buro"
                tabIndex={-1}
            >
                <div ref={heroRef} className={styles.hero} data-hero-peek-pinned="false">
                    <div className={styles.heroMedia}>
                        <Image
                            src="/Шапка.webp"
                            alt=""
                            fill
                            priority
                            loading="eager"
                            sizes="(max-width: 560px) calc(100vw - 5px), 555px"
                            className={styles.heroImage}
                        />
                    </div>
                </div>

                <div className={styles.content}>
                    <div className={styles.opening}>
                        <div className={styles.identity}>
                            <p className={styles.identityLead}>мы</p>
                            <p className={styles.identityBrand}>GARMENT BURO</p>
                        </div>

                        <p className={styles.statement}>
                            — делаем общий мерч личным для
                            <br />
                            каждого.
                        </p>

                        <div className={styles.intro}>
                            <p>
                                У клубной одежды есть противоречие: она должна показывать, что вы вместе, но не делать всех одинаковыми.
                            </p>
                            <p>
                                Мы решили проверить, что произойдёт, если продолжить эту мысль внутри продукта
                                <br />
                                <br />
                                <span className={styles.platform}>—&nbsp;&nbsp;&nbsp;Платформа</span>
                            </p>
                        </div>

                        <blockquote className={styles.quote}>
                            «Когда мы собираемся, всегда кажется, что эти люди не должны были оказаться вместе. Наверное, поэтому нам так хорошо»
                        </blockquote>

                        <p className={styles.author}>Алексей Джипитиев</p>

                        <h1 className={styles.nextTitle}>
                            одежда
                            <br />
                            — это повод собраться?
                        </h1>
                    </div>

                    <PresentationRoadmap />
                </div>
            </section>
        </div>
    );
}
