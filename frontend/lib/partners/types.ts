export type PartnerProfile = {
    id: number;
    user_id: number;
    code: string;
    display_name: string;
    status: 'invited' | 'active' | 'suspended';
    commission_bps: number;
    created_at: string;
};

export type PartnerDashboard = {
    partner: PartnerProfile;
    visits: number;
    orders: number;
    conversion_percent: string;
    earned: string;
    available: string;
    paid: string;
    currency: 'RUB';
};

export type PartnerLanding = {
    id: number;
    slug: string;
    title: string;
    eyebrow?: string;
    headline: string;
    description: string;
    cta_label: string;
    cta_href: string;
    image_url?: string;
    product_ids: number[];
    status: 'draft' | 'published' | 'archived';
    published_at?: string;
    created_at: string;
    updated_at: string;
};

export type PublicPartnerLanding = Omit<PartnerLanding,
    'id' | 'status' | 'published_at' | 'created_at' | 'updated_at'
> & {
    partner_name: string;
};

export type PartnerCommission = {
    id: number;
    order_id: number;
    amount: string;
    currency: 'RUB';
    status: 'pending' | 'canceled';
    available_at: string;
    created_at: string;
};

export type PartnerPayout = {
    id: number;
    amount: string;
    currency: 'RUB';
    status: 'requested' | 'approved' | 'paid' | 'rejected' | 'canceled';
    reviewed_at?: string;
    paid_at?: string;
    note?: string;
    created_at: string;
};

export type PartnerCreatePayload = {
    email: string;
    code: string;
    display_name: string;
    commission_bps: number;
    status: 'invited' | 'active';
};

export type PartnerLandingCreatePayload = {
    slug: string;
    title: string;
    eyebrow?: string;
    headline: string;
    description: string;
    cta_label: string;
    cta_href: string;
    image_url?: string;
    product_ids: number[];
    status: 'draft' | 'published';
};
