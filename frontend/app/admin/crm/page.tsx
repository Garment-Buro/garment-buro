import { notFound } from 'next/navigation';

import { CrmProjectsScreen } from '@/components/admin/CrmProjectsScreen';
import { isCrmCabinetEnabled } from '@/lib/auth/config';

export default function CrmProjectsPage() {
    if (!isCrmCabinetEnabled()) notFound();
    return <CrmProjectsScreen />;
}
