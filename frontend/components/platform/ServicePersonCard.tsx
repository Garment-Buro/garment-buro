import Link from 'next/link';
import {PublicAvatar} from '@/components/people/PublicAvatar';
import {personHref,publicAvatarHref,type PublicPerson} from '@/lib/catalog/people';
import styles from './ServiceHome.module.css';

export function ServicePersonCard({person}: {person:PublicPerson}) {
    return <article className={styles.personCard} data-person={person.id}>
        <div className={styles.personPortrait}>
            <PublicAvatar src={publicAvatarHref(person, 'card')} name={person.display_name} className={styles.personPhoto}/>
        </div>
        <div className={styles.personDetails}>
            <h3>{person.display_name}</h3>
            <p>{person.bio || `@${person.slug}`}</p>
        </div>
        <Link href={personHref(person.slug)} prefetch={false} className={styles.cardOpen} aria-label={`${person.display_name}: открыть профиль`}/>
    </article>;
}
