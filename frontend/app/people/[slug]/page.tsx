import type {Metadata} from 'next';
import {notFound} from 'next/navigation';
import {getPublicPerson} from '@/lib/server/backend/people';
import {validatePersonSlug} from '@/lib/catalog/people';
import {PublicPersonView} from '@/components/people/PublicPersonView';

export const dynamic='force-dynamic';
export const metadata:Metadata={title:'Публичный профиль'};

export default async function PersonPage({params}:{params:Promise<{slug:string}>}) {
    const {slug}=await params;
    try {validatePersonSlug(slug)} catch {notFound()}
    const person=await getPublicPerson(slug);
    if (!person) notFound();
    return <PublicPersonView person={person}/>;
}
