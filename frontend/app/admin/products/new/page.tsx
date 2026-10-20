import { redirect } from 'next/navigation';

export default function Page() {
    redirect('/production?section=presets&product=new');
}
