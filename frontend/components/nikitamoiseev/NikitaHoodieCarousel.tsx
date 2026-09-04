'use client';

import Image from 'next/image';
import { useEffect, useRef, useState } from 'react';

import styles from './NikitaMoiseevLanding.module.css';

const slides = [
    {
        src: '/nikitamoiseev/hoodie-front.png',
        alt: 'Худи Moving Castle, основной вид',
        className: styles.slideMain,
    },
    {
        src: '/nikitamoiseev/hoodie-front.png',
        alt: 'Вышивка Moving Castle крупным планом',
        className: styles.slideDetail,
    },
    {
        src: '/nikitamoiseev/hoodie-back-model.png',
        alt: 'Худи Moving Castle на модели',
        className: styles.slideModel,
    },
    {
        src: '/nikitamoiseev/hoodie-back-model.png',
        alt: 'Деталь спины худи Moving Castle',
        className: styles.slideModelDetail,
    },
];

export const NikitaHoodieCarousel = () => {
    const trackRef = useRef<HTMLDivElement>(null);
    const frameRef = useRef<number | null>(null);
    const [activeSlide, setActiveSlide] = useState(0);

    useEffect(() => () => {
        if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    }, []);

    const updateActiveSlide = () => {
        if (frameRef.current !== null) return;
        frameRef.current = requestAnimationFrame(() => {
            frameRef.current = null;
            const track = trackRef.current;
            if (!track?.clientWidth) return;
            setActiveSlide(Math.round(track.scrollLeft / track.clientWidth));
        });
    };

    const showSlide = (index: number) => {
        const track = trackRef.current;
        if (!track) return;
        const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        track.scrollTo({ left: track.clientWidth * index, behavior: reducedMotion ? 'auto' : 'smooth' });
        setActiveSlide(index);
    };

    return (
        <div className={styles.carousel} aria-roledescription="carousel" aria-label="Образы худи Moving Castle">
            <div ref={trackRef} className={styles.carouselTrack} onScroll={updateActiveSlide}>
                {slides.map((slide, index) => (
                    <figure
                        key={`${slide.src}-${index}`}
                        className={styles.carouselSlide}
                        aria-label={`${index + 1} из ${slides.length}`}
                    >
                        <Image
                            src={slide.src}
                            alt={slide.alt}
                            fill
                            priority={index === 0}
                            sizes="(max-width: 767px) 100vw, 0px"
                            className={slide.className}
                        />
                    </figure>
                ))}
            </div>

            <div className={styles.carouselDots} aria-label="Выбор изображения">
                {slides.map((slide, index) => (
                    <button
                        key={`${slide.alt}-dot`}
                        type="button"
                        aria-label={`Показать изображение ${index + 1}`}
                        aria-current={activeSlide === index ? 'true' : undefined}
                        onClick={() => showSlide(index)}
                    >
                        <Image src="/nikitamoiseev/slider-dot.svg" alt="" width={9} height={7} />
                    </button>
                ))}
            </div>
            <Image
                src="/nikitamoiseev/hoodie-shadow.svg"
                alt=""
                width={321}
                height={25}
                className={styles.hoodieShadow}
            />
        </div>
    );
};
