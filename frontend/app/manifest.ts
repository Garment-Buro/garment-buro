import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
    return {
        name: "Garment Buro",
        short_name: "Garment Buro",
        description: "Когда вещь почти подходит — можно её доработать.",
        start_url: "/",
        display: "standalone",
        background_color: "#F2F2F2",
        theme_color: "#F2F2F2",
        icons: [
            {
                src: "/pwa-icon-192.png",
                sizes: "192x192",
                type: "image/png",
                purpose: "any",
            },
            {
                src: "/pwa-icon-192.png",
                sizes: "192x192",
                type: "image/png",
                purpose: "maskable",
            },
            {
                src: "/pwa-icon-512.png",
                sizes: "512x512",
                type: "image/png",
                purpose: "any",
            },
            {
                src: "/pwa-icon-512.png",
                sizes: "512x512",
                type: "image/png",
                purpose: "maskable",
            },
        ],
    };
}
