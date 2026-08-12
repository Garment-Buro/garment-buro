import type { Metadata } from "next";
import { notFound } from "next/navigation";
import ConstructorPage from "@/components/constructor/ConstructorPage";
import Home from "../page";

type ConstructorRoutePageProps = {
    params: Promise<{
        constructorRoute: string;
    }>;
    searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

const getSearchParam = (
    params: Record<string, string | string[] | undefined>,
    ...keys: string[]
) => {
    for (const key of keys) {
        const value = params[key];
        if (Array.isArray(value)) return value[0] || null;
        if (value) return value;
    }

    return null;
};

export async function generateMetadata({ params }: ConstructorRoutePageProps): Promise<Metadata> {
    const { constructorRoute } = await params;

    return {
        title: constructorRoute === "index" ? "Главная" : "Конструктор",
    };
}

export default async function ConstructorRoutePage({ params, searchParams }: ConstructorRoutePageProps) {
    const { constructorRoute } = await params;

    if (constructorRoute === "index") {
        return <Home />;
    }

    if (constructorRoute !== "constructor") {
        notFound();
    }

    const resolvedSearchParams = searchParams ? await searchParams : {};

    return (
        <ConstructorPage
            productId={getSearchParam(resolvedSearchParams, "productId", "product", "id")}
            editCartItemId={getSearchParam(resolvedSearchParams, "editCartItemId")}
            draftId={getSearchParam(resolvedSearchParams, "draftId")}
        />
    );
}
