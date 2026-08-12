"use client";

import { ConstructorWorkspace } from '@/components/constructor/ConstructorWorkspace';
import { useConstructorPageController } from '@/hooks/constructor/useConstructorPageController';
import type { ConstructorPageProps } from '@/lib/constructor/types';

export default function ConstructorPage(props: ConstructorPageProps = {}) {
    const controller = useConstructorPageController(props);
    return <ConstructorWorkspace controller={controller} />;
}

