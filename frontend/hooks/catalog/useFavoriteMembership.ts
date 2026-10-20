'use client';

import { getFavoriteStatus, setProductFavorite } from '@/lib/api/favorites';
import {useCustomerFavoriteMembership} from './useCustomerFavoriteMembership';

const api={status:getFavoriteStatus,save:setProductFavorite};

export function useFavoriteMembership(productIds: readonly number[]) {
    return useCustomerFavoriteMembership(productIds,api);
}
