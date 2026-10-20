import { redirect } from 'next/navigation';

// An old bookmark cannot establish that a particular order was created or paid.
export default function OrderSuccessPage() {
    redirect('/profile');
}
