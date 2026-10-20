import 'server-only';

import {getInitialStorefront} from '@/lib/server/backend/storefront';
import {getInitialCommunities} from '@/lib/server/backend/communities';
import {getInitialPeople} from '@/lib/server/backend/people';
import {PlatformEntry} from './PlatformEntry';
import {createCatalogQuery, defaultFilters} from './serviceCatalog';

export async function ServerPlatformEntry({catalog = false}: {catalog?: boolean}) {
    const [initialProducts,initialCommunities,initialPeople] = await Promise.all([
        getInitialStorefront(catalog ? createCatalogQuery('', defaultFilters) : {limit:4}),
        catalog ? undefined : getInitialCommunities({limit:4}),
        catalog ? undefined : getInitialPeople({limit:4}),
    ]);
    return <PlatformEntry initialCategory={catalog ? 'clothing' : null} initialProducts={initialProducts} initialCommunities={initialCommunities} initialPeople={initialPeople} />;
}
