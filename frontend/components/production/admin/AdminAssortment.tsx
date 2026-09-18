'use client';

import { useState } from 'react';
import {
    PiArchive,
    PiBlueprint,
    PiPackage,
    PiScissors,
    PiTShirt,
    PiWrench,
    PiYarn,
} from 'react-icons/pi';
import {
    assortmentLabels,
    type AssortmentSection,
} from '@/lib/production/assortmentTypes';
import { AdminAccessories } from './assortment/AdminAccessories';
import { AdminBoxes } from './assortment/AdminBoxes';
import { AdminFabrics } from './assortment/AdminFabrics';
import { AdminModels } from './assortment/AdminModels';
import { AdminPatterns } from './assortment/AdminPatterns';
import { AdminProducts } from './assortment/AdminProducts';
import { AdminTechCards } from './assortment/AdminTechCards';
import styles from './ProductionAdmin.module.css';

const icons = {
    models: PiTShirt,
    patterns: PiScissors,
    techCards: PiBlueprint,
    fabrics: PiYarn,
    accessories: PiWrench,
    boxes: PiPackage,
    products: PiArchive,
};

export function AdminAssortment() {
    const [section, setSection] = useState<AssortmentSection>('models');
    const Current = {
        models: AdminModels,
        patterns: AdminPatterns,
        techCards: AdminTechCards,
        fabrics: AdminFabrics,
        accessories: AdminAccessories,
        boxes: AdminBoxes,
        products: AdminProducts,
    }[section];

    return (
        <section>
            <div className={styles.sectionHeading}>
                <div>
                    <h2>Товары и склад</h2>
                    <p className={styles.muted}>
                        Модели, производство, материалы, упаковка и каталог в
                        одном месте.
                    </p>
                </div>
            </div>
            <nav className={styles.subnav} aria-label="Разделы товаров и склада">
                {(Object.keys(assortmentLabels) as AssortmentSection[]).map(
                    (key) => {
                        const Icon = icons[key];
                        return (
                            <button
                                key={key}
                                type="button"
                                aria-current={section === key ? 'page' : undefined}
                                onClick={() => setSection(key)}
                            >
                                <Icon aria-hidden />
                                {assortmentLabels[key]}
                            </button>
                        );
                    },
                )}
            </nav>
            <div className={styles.assortmentWorkspace}>
                <Current />
            </div>
        </section>
    );
}
