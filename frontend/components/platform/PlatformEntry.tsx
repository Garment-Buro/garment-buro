import { ServiceHome } from './ServiceHome';
import type { ServiceCategory } from './serviceHomeData';
import type {StorefrontInitial} from '@/lib/catalog/storefront';
import type {CommunityInitial} from '@/lib/catalog/communities';
import type {PeopleInitial} from '@/lib/catalog/people';

export const PlatformEntry = ({ initialCategory = null, initialProducts, initialCommunities, initialPeople }: { initialCategory?: ServiceCategory | null; initialProducts?:StorefrontInitial; initialCommunities?:CommunityInitial; initialPeople?:PeopleInitial }) => (
    <ServiceHome key={initialCategory ?? 'home'} initialCategory={initialCategory} initialProducts={initialProducts} initialCommunities={initialCommunities} initialPeople={initialPeople} />
);
