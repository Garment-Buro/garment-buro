export const isIdentitySessionV2Enabled = () => (
    process.env.NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED === 'true'
);

export const isCatalogWritesV2Enabled = () => (
    process.env.NEXT_PUBLIC_CATALOG_WRITES_ENABLED === 'true'
);

export const isCrmCabinetEnabled = () => (
    process.env.NEXT_PUBLIC_CRM_CABINET_ENABLED === 'true'
);
