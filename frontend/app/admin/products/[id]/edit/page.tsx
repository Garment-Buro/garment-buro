import { notFound, redirect } from 'next/navigation';

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
    const { id } = await params;
    if (!/^[1-9]\d*$/.test(id) || Number(id) > 2147483647) notFound();
    redirect(`/production?section=presets&product=${id}`);
}
