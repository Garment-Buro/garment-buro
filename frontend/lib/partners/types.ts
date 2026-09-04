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
    partner_id: number;
    slug: string;
    title: string;
    eyebrow?: string;
    headline: string;
    description: string;
    cta_label: string;
    cta_href: string;
    image_url?: string;
    template_key: 'light-running';
    content: PartnerLandingContent;
    product_ids: number[];
    status: 'draft' | 'published' | 'archived';
    published_at?: string;
    created_at: string;
    updated_at: string;
};

export type PartnerLandingFaqItem = {
    question: string;
    answer: string;
};

export type PartnerLandingContent = {
    logo_url?: string;
    secondary_image_url?: string;
    story_title?: string;
    story_body?: string;
    model_heading?: string;
    proof_line?: string;
    final_heading?: string;
    faq: PartnerLandingFaqItem[];
};

export type PublicPartnerLanding = Omit<PartnerLanding,
    'id' | 'partner_id' | 'status' | 'published_at' | 'created_at' | 'updated_at'
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

export type PartnerEntityType = 'self_employed' | 'sole_proprietor' | 'legal_entity';

export type PartnerRequisitesPayload = {
    entity_type: PartnerEntityType;
    recipient_name: string;
    tax_id: string;
    kpp?: string | null;
    bank_name: string;
    bic: string;
    correspondent_account: string;
    settlement_account: string;
};

export type PartnerRequisites = PartnerRequisitesPayload & {
    updated_at: string;
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
    template_key: 'light-running';
    content: PartnerLandingContent;
    product_ids: number[];
    status: 'draft' | 'published';
};

export type PartnerLandingUpdatePayload = Partial<Omit<PartnerLandingCreatePayload, 'slug'>>;
