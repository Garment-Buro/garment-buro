import { ServiceCatalogIcon } from './ServiceCatalogIcon';
import { ServiceCommunityCatalog } from './ServiceCommunityCatalog';
import { ServicePersonCard } from './ServicePersonCard';
import { serviceCategoryLabels, servicePeople, type ServiceCategory } from './serviceHomeData';
import { rankServiceItems } from './serviceSearch';
import resultStyles from './ServiceSearchResults.module.css';
import styles from './ServiceCategoryCatalog.module.css';

export function ServiceCategoryCatalog({ category, query, onBack }: {
    category: Exclude<ServiceCategory, 'clothing'>;
    query: string;
    onBack: () => void;
}) {
    if (category === 'communities') return <ServiceCommunityCatalog query={query} onBack={onBack} />;

    return <section className={resultStyles.results} aria-labelledby="category-catalog-title">
        <div className={resultStyles.toolbar}>
            <button type="button" onClick={onBack} aria-label="Вернуться на главную"><ServiceCatalogIcon name="back" width={15} height={13} /></button>
            <h2 id="category-catalog-title">{serviceCategoryLabels[category]}</h2>
        </div>
        <div className={resultStyles.scroller} role="group" tabIndex={0} aria-label={`Каталог: ${serviceCategoryLabels[category].toLocaleLowerCase('ru')}`}>
            <div className={styles.people}>
                {rankServiceItems(servicePeople, query).map(person => <ServicePersonCard key={person.id} person={person} />)}
            </div>
        </div>
    </section>;
}
