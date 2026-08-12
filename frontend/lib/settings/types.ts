export interface LandingSettings {
    logo_video_url: string;
    hero_products: number[];
    showroom1_products: number[];
    showroom2_products: number[];
    links: Record<string, { label: string; url: string }>;
}
