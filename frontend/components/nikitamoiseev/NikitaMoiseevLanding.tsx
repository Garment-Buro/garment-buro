import { NikitaDesktopGate } from './NikitaDesktopGate';
import { NikitaMobileDrop } from './NikitaMobileDrop';
import styles from './NikitaMoiseevLanding.module.css';

export const NikitaMoiseevLanding = () => (
    <article className={styles.page}>
        <a className={styles.skipLink} href="#nikita-drop">Перейти к коллекции</a>
        <NikitaMobileDrop />
        <NikitaDesktopGate />
    </article>
);
