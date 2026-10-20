'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { getOwnPublicProfile } from '@/lib/api/people';
import { useCustomerAccount, runForCustomer } from '@/hooks/catalog/customerSession';
import styles from './PublicPerson.module.css';

export function OwnProfileLink({ profileId }: { profileId: number }) {
    const { key, userId } = useCustomerAccount();
    const [owner, setOwner] = useState<{ key: string; id: number } | null>(null);
    useEffect(() => {
        if (key === null || userId === null) return;
        const controller = new AbortController();
        void runForCustomer(userId, token => getOwnPublicProfile(token, controller.signal), key)
            .then(profile => { if (!controller.signal.aborted && profile) setOwner({ key, id: profile.id }); })
            .catch(() => { /* The optional owner link never changes public availability. */ });
        return () => controller.abort();
    }, [key, userId]);
    return key !== null && owner?.key === key && owner.id === profileId
        ? <Link className={styles.secondary} href="/profile/public" prefetch={false}>Редактировать мой профиль</Link> : null;
}
