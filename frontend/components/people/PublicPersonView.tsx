import Link from 'next/link';
import {publicAvatarHref,type PublicPerson} from '@/lib/catalog/people';
import {PublicAvatar} from './PublicAvatar';
import {OwnProfileLink} from './OwnProfileLink';
import styles from './PublicPerson.module.css';

export function PublicPersonView({person}:{person:PublicPerson}) {
    return <section className={styles.page} aria-labelledby="public-person-name">
        <Link href="/" prefetch={false} className={styles.back}>← На главную</Link>
        <article className={styles.profile} data-public-person={person.id}>
            <PublicAvatar src={publicAvatarHref(person)} name={person.display_name} className={styles.avatar} eager/>
            <div className={styles.content}>
                <p className={styles.eyebrow}>ПУБЛИЧНЫЙ ПРОФИЛЬ</p>
                <h1 id="public-person-name">{person.display_name}</h1>
                <p className={styles.slug}>@{person.slug}</p>
                {person.bio && <p className={styles.bio}>{person.bio}</p>}
                <OwnProfileLink profileId={person.id}/>
            </div>
        </article>
    </section>;
}
