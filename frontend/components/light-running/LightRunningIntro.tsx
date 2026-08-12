import Image from "next/image";
import Link from "next/link";

import { LightRunningCartAction } from "./LightRunningCartAction";
import styles from "./LightRunningIntro.module.css";

function TriangleMark({ rotated = false }: { rotated?: boolean }) {
    return (
        <svg
            className={rotated ? styles.triangleRotated : styles.triangle}
            viewBox="0 0 7 4"
            fill="none"
            aria-hidden="true"
        >
            <path d="M7 2L-6.51683e-07 4L-4.76837e-07 -3.0598e-07L7 2Z" fill="currentColor" />
        </svg>
    );
}

export function LightRunningIntro() {
    return (
        <article className={styles.page}>
            <Image
                src="/Лого-LR.webp"
                alt="Light Running"
                width={304}
                height={63}
                priority
                className={styles.logo}
            />

            <div className={styles.brandLine} aria-label="Light Running × RAUM">
                <TriangleMark rotated />
                <Image
                    src="/RAUM.svg"
                    alt="RAUM"
                    width={24}
                    height={7}
                    className={styles.raum}
                />
                <TriangleMark />
            </div>

            <div className={styles.runners}>
                <Image
                    src="/Бегуны-черные.webp"
                    alt=""
                    fill
                    priority
                    unoptimized
                    sizes="(max-width: 370px) 251px, (max-width: 560px) calc(23.158vw + 165.316px), 295px"
                    className={styles.runnersImage}
                />
            </div>

            <div className={styles.copy}>
                <div className={styles.sloganRow}>
                    <TriangleMark />
                    <p className={styles.slogan}>
                        RUN IN LIGHT
                        <br />
                        FIND YOUR SPACE
                        <br />
                        BEYOND LIMITS
                    </p>
                </div>

                <p className={styles.description}>
                    Беговое сообщество.
                    <br />
                    Технологичная экипировка.
                </p>
            </div>

            <div className={styles.runInLightBand} aria-hidden="true" />

            <div
                id="light-running-run-in-light"
                className={styles.runInLightLabel}
            >
                <TriangleMark />
                <p className={styles.runInLightText}>RUN IN LIGHT</p>
            </div>

            <div
                id="light-running-model"
                className={styles.modelImageBlock}
            >
                <Image
                    src="/Модель-в-майке-расширенно.webp"
                    alt="Модель в экипировке Light Running"
                    fill
                    unoptimized
                    sizes="100vw"
                    className={styles.modelImage}
                />
                <div className={styles.modelBottomFade} aria-hidden="true" />

                <div className={styles.modelLightMessage}>
                    <p>
                        LIGHT
                        <br />
                        DRIVES US
                    </p>
                    <TriangleMark />
                </div>

                <p className={styles.modelMonogram}>LR</p>

                <Link
                    href="/constructor?productId=1"
                    prefetch={false}
                    className={styles.customizeButton}
                >
                    <div className={styles.customizeButtonContent}>
                        <span className={styles.customizeButtonText}>Настроить мерч</span>
                        <svg
                            className={styles.customizeButtonArrow}
                            viewBox="0 0 18 14"
                            fill="none"
                            aria-hidden="true"
                        >
                            <path
                                d="M10 13L17 7.00001L10 1"
                                stroke="#141414"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                            />
                            <path
                                d="M15 6.99903L1 6.99902"
                                stroke="#141414"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                            />
                        </svg>
                    </div>
                </Link>
            </div>

            <LightRunningCartAction />
        </article>
    );
}
