"use client";

import Image from "next/image";
import type { CSSProperties } from "react";
import { useEffect, useRef, useState } from "react";

import styles from "./PresentationRoadmap.module.css";

const ROADMAP_STEPS = [
    {
        title: "Настрой посадку",
        captionLines: ["Приходи в общем —", "оставайся в своём!"],
        imageSrc: "/1.webp",
        displayWidth: 217,
        displayHeight: 298,
    },
    {
        title: "Добавь кастом",
        captionLines: ["Приходи в общем —", "оставайся в своём!"],
        imageSrc: "/2.webp",
        displayWidth: 240,
        displayHeight: 357,
    },
    {
        title: "Создай профиль",
        captionLines: ["Участников должно", "быть видно!"],
        imageSrc: "/3.webp",
        displayWidth: 182,
        displayHeight: 295,
    },
    {
        title: "Крути каталог",
        captionLines: ["Возможно вам", "по пути!", "Здесь видно,", "что создают", "другие."],
        imageSrc: "/4.webp",
        displayWidth: 195,
        displayHeight: 315,
    },
    {
        title: "Будь в курсе",
        captionLines: ["Чтобы понять", "сообщество,", "мало увидеть", "его мерч."],
        imageSrc: "/5.webp",
        displayWidth: 258,
        displayHeight: 435,
    },
];

const ROADMAP_VIDEOS = [
    {
        src: "/девушка бежит3.mp4",
        width: 52,
        height: 132,
        marginLeft: 40,
        marginTop: 0,
    },
    {
        src: "/парень бежит.mp4",
        width: 63,
        height: 131,
        marginLeft: -13,
        marginTop: 66,
    },
    {
        src: "/дед бежит.mp4",
        width: 74,
        height: 129,
        marginLeft: 40,
        marginTop: 130,
    },
];

export function PresentationRoadmap() {
    const sectionRef = useRef<HTMLElement>(null);
    const stepRefs = useRef<Array<HTMLElement | null>>([]);
    const [activeStepIndex, setActiveStepIndex] = useState(0);
    const [activeVideoIndex, setActiveVideoIndex] = useState(0);
    const activeCaptionLines = ROADMAP_STEPS[activeStepIndex]?.captionLines ?? ROADMAP_STEPS[0].captionLines;

    useEffect(() => {
        const section = sectionRef.current;
        const scrollContainer = section?.closest<HTMLElement>('[data-presentation-sheet]');

        if (!scrollContainer) return;
        const isOverlay = scrollContainer.getAttribute('role') === 'dialog';
        const scrollTarget = isOverlay ? scrollContainer : window;

        let animationFrame = 0;

        const updateActiveStep = () => {
            animationFrame = 0;

            const sheetTop = isOverlay ? scrollContainer.getBoundingClientRect().top : 0;
            const heroPeekHeight = Number.parseFloat(
                getComputedStyle(scrollContainer).getPropertyValue("--presentation-hero-peek"),
            ) || 97;
            const activationLine = sheetTop + heroPeekHeight + 73;
            const boyActivationLine = activationLine + 100;
            const grandpaActivationLine = activationLine + 160;
            let nextActiveIndex = 0;
            let nextActiveVideoIndex = 0;

            stepRefs.current.forEach((step, index) => {
                if (step && step.getBoundingClientRect().top <= activationLine + 1) {
                    nextActiveIndex = index;
                }
            });

            const isAtScrollEnd = (
                isOverlay
                    ? scrollContainer.scrollTop + scrollContainer.clientHeight >= scrollContainer.scrollHeight - 1
                    : window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 1
            );

            if (isAtScrollEnd) {
                nextActiveIndex = ROADMAP_STEPS.length - 1;
            }

            if (
                stepRefs.current[0]
                && stepRefs.current[0].getBoundingClientRect().top <= boyActivationLine
            ) {
                nextActiveVideoIndex = 1;
            }

            if (
                stepRefs.current[1]
                && stepRefs.current[1].getBoundingClientRect().top <= grandpaActivationLine
            ) {
                nextActiveVideoIndex = ROADMAP_VIDEOS.length - 1;
            }

            setActiveStepIndex((currentIndex) => (
                currentIndex === nextActiveIndex ? currentIndex : nextActiveIndex
            ));
            setActiveVideoIndex((currentIndex) => (
                currentIndex === nextActiveVideoIndex ? currentIndex : nextActiveVideoIndex
            ));
        };

        const scheduleUpdate = () => {
            if (animationFrame) return;
            animationFrame = window.requestAnimationFrame(updateActiveStep);
        };

        updateActiveStep();
        scrollTarget.addEventListener("scroll", scheduleUpdate, { passive: true });
        window.addEventListener("resize", scheduleUpdate);

        return () => {
            scrollTarget.removeEventListener("scroll", scheduleUpdate);
            window.removeEventListener("resize", scheduleUpdate);
            window.cancelAnimationFrame(animationFrame);
        };
    }, []);

    return (
        <section ref={sectionRef} className={styles.section} aria-labelledby="presentation-roadmap-title">
            <h2 className={styles.decision}>если да то:</h2>

            <div className={styles.layout}>
                <div className={styles.mediaColumn}>
                    <div className={styles.heading}>
                        <h3 id="presentation-roadmap-title" className={styles.title}>
                            дорожная карта
                        </h3>
                        <Image
                            src="/map_arrow.svg"
                            alt=""
                            width={15}
                            height={24}
                            className={styles.arrow}
                        />
                    </div>

                    <p className={styles.mediaCaption} data-roadmap-caption-index={activeStepIndex}>
                        {activeCaptionLines.map((line) => (
                            <span className={styles.mediaCaptionLine} key={line}>
                                {line}
                            </span>
                        ))}
                    </p>

                    <div className={styles.videoStage} data-roadmap-video-stage>
                        {ROADMAP_VIDEOS.map((video, index) => (
                            <video
                                key={video.src}
                                className={`${styles.video} ${
                                    index <= activeVideoIndex ? styles.videoActive : ""
                                }`}
                                src={video.src}
                                width={video.width}
                                height={video.height}
                                style={{
                                    "--roadmap-video-width": `${video.width}px`,
                                    "--roadmap-video-height": `${video.height}px`,
                                    "--roadmap-video-margin-left": `${video.marginLeft}px`,
                                    "--roadmap-video-margin-top": `${video.marginTop}px`,
                                } as CSSProperties}
                                autoPlay
                                muted
                                loop
                                playsInline
                                preload={index <= activeVideoIndex ? "auto" : "metadata"}
                                aria-hidden={index > activeVideoIndex}
                                data-roadmap-video={index}
                            />
                        ))}
                    </div>
                </div>

                <div className={styles.steps}>
                    {ROADMAP_STEPS.map((step, index) => (
                        <article
                            ref={(node) => {
                                stepRefs.current[index] = node;
                            }}
                            className={styles.step}
                            key={step.imageSrc}
                            data-roadmap-step={index}
                        >
                            <p className={styles.stepText}>{step.title}</p>
                            <div
                                className={styles.stepImage}
                                style={{
                                    "--roadmap-step-width": `${(step.displayWidth / 258) * 100}%`,
                                    "--roadmap-step-ratio": `${step.displayWidth} / ${step.displayHeight}`,
                                } as CSSProperties}
                            >
                                <Image
                                    src={step.imageSrc}
                                    alt=""
                                    fill
                                    sizes="(max-width: 560px) 47vw, 258px"
                                    className={styles.stepImageAsset}
                                />
                            </div>
                        </article>
                    ))}
                </div>
            </div>
        </section>
    );
}
