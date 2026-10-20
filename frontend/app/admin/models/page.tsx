import { redirect } from 'next/navigation';

export default function AdminModelsPage() {
    redirect('/production?section=presets');
}
