import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
    return {
        // Keep the installed application identity while changing its launch page.
        id: "/constructor",
        name: "Garment Buro",
        short_name: "Garment Buro",
        description: "Сообщества, одежда и люди Garment Buro.",
        start_url: "/?source=pwa",
        scope: "/",
        display: "standalone",
        orientation: "portrait-primary",
        lang: "ru",
        background_color: "#77745A",
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
