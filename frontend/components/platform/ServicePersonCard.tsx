import Image, { type StaticImageData } from 'next/image';

import styles from './ServiceHome.module.css';

export type ServicePerson = {
    id: string;
    name: string;
    subtitle: string;
    image: StaticImageData | { src: string; width: number; height: number };
    portrait: 'lizaPortrait' | 'manPortrait';
};

export function ServicePersonCard({ person, onOpen }: { person: ServicePerson; onOpen?: () => void }) {
    return <article className={styles.personCard}>
        <Image src={person.image} alt="" loading="eager" unoptimized className={`${styles.cropImage} ${styles.personBackdrop}`} />
        <div className={styles.personPortrait}>
            <Image src={person.image} alt={person.name} loading="eager" unoptimized className={`${styles.cropImage} ${styles[person.portrait]}`} />
        </div>
        <div className={styles.personDetails}>
            <h3>{person.name}</h3>
            <p>{person.subtitle}</p>
        </div>
        {onOpen && <button type="button" className={styles.cardOpen} aria-label={`${person.name}: открыть каталог людей`} onClick={onOpen} />}
    </article>;
}
