import Link from 'next/link';

import { LandingReveal, LandingWordReveal } from '@/components/landings/LandingReveal';

import styles from './PlatformHome.module.css';

const capabilities = [
    ['Коллекция', 'Вместе с автором выбираем идею и модели для запуска.'],
    ['Лендинг', 'Собираем отдельную страницу в визуальном языке партнёра.'],
    ['Конструктор', 'Покупатель меняет посадку, цвет и детали изделия.'],
    ['Производство', 'Берём на себя изготовление, оплату и логистику заказа.'],
];

export const PlatformHome = () => (
    <div className={styles.page}>
        <a className={styles.skipLink} href="#platform-content">Перейти к содержанию</a>
        <header className={styles.header}>
            <Link href="/" className={styles.wordmark}>GARMENT BURO</Link>
            <nav aria-label="Сервисы платформы">
                <Link href="/profile">Личный кабинет</Link>
                <Link href="https://partner.garment-buro.ru">Партнёрам</Link>
            </nav>
        </header>

        <main id="platform-content">
            <section className={styles.hero} aria-labelledby="platform-title">
                <p className={styles.marker}>Платформа совместных коллекций</p>
                <h1 id="platform-title">Создаём одежду вместе с авторами и сообществами</h1>
                <p className={styles.lead}>
                    Вы приносите аудиторию и идею. Мы собираем лендинг, даём покупателям конструктор,
                    производим заказы и организуем доставку.
                </p>
                <Link className={styles.primaryButton} href="/contacts">Обсудить коллекцию</Link>
                <p className={styles.proof}>Собственное производство и логистика GARMENT BURO</p>
            </section>

            <section className={styles.taglineSection} aria-label="Главная идея">
                <LandingWordReveal text="Один автор. Одна коллекция. Тысячи вещей, настроенных под конкретных людей." />
            </section>

            <section className={styles.capabilities} aria-labelledby="capabilities-title">
                <LandingReveal className={styles.sectionHeading}>
                    <p className={styles.marker}>Что мы собираем</p>
                    <h2 id="capabilities-title">Полный путь от идеи до заказа</h2>
                </LandingReveal>
                <div className={styles.capabilityList}>
                    {capabilities.map(([title, description], index) => (
                        <LandingReveal key={title}>
                            <article className={styles.capability}>
                                <span>{String(index + 1).padStart(2, '0')}</span>
                                <h3>{title}</h3>
                                <p>{description}</p>
                            </article>
                        </LandingReveal>
                    ))}
                </div>
            </section>

            <section className={styles.audiences} aria-labelledby="audiences-title">
                <LandingReveal>
                    <p className={styles.marker}>Кому подходит</p>
                    <h2 id="audiences-title">Блогерам, брендам, производствам и сообществам</h2>
                    <p>
                        Каждая коллекция получает собственный адрес, визуальный язык и набор моделей.
                        Покупатели регистрируются в общей платформе и сохраняют дизайны в личном кабинете.
                    </p>
                    <Link className={styles.secondaryButton} href="/contacts">Запустить первую коллекцию</Link>
                </LandingReveal>
            </section>
        </main>

        <footer className={styles.footer}>
            <p>GARMENT BURO</p>
            <nav aria-label="Правовая информация">
                <Link href="/offer">Оферта</Link>
                <Link href="/policy">Политика</Link>
                <Link href="/contacts">Контакты</Link>
            </nav>
        </footer>
    </div>
);
