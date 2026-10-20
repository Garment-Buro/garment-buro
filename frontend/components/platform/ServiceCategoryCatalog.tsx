import { ServiceCommunityCatalog } from './ServiceCommunityCatalog';
import { ServicePeopleCatalog } from './ServicePeopleCatalog';
import type {ServiceCategory} from './serviceHomeData';

export function ServiceCategoryCatalog({ category, query, onBack }: {
    category: Exclude<ServiceCategory, 'clothing'>;
    query: string;
    onBack: () => void;
}) {
    return category === 'communities' ? <ServiceCommunityCatalog query={query} onBack={onBack} />
        : <ServicePeopleCatalog query={query} onBack={onBack} />;
}
