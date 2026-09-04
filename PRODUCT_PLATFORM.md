# GARMENT BURO partner collection platform

## Product model

The public product is a network of partner collection landings. A blogger, community,
brand, or production partner brings an audience and a collection idea. GARMENT BURO
provides the landing system, garment constructor, checkout, manufacturing, and delivery.

## Primary user journey

1. A visitor opens `/p/{slug}` from a partner link.
2. The landing records privacy preserving attribution and shows only the models selected
   for that collection.
3. The visitor opens `/constructor?productId={id}&landing={slug}` and customizes a model.
4. The design is saved to `UNFINISHED`; checkout authenticates the visitor when needed.
5. Paid items appear in `MY COLLECTION`; account data and support live in `PROFILE`.
6. The paid order accrues the partner commission after the configured hold period.

## Product surfaces

| Surface | Route | Responsibility |
| --- | --- | --- |
| Platform presentation | `/` | Explain the collaboration model without a public catalog |
| Partner collection | `/p/{slug}` | Tell the collection story and open selected models in the constructor |
| Constructor | `/constructor` | Customize an internal garment model |
| Cart and checkout | `/checkout` | Authenticate, deliver, and pay |
| Customer cabinet | `/unfinished`, `/mycollection`, `/profile` | Drafts, purchased collection, and account |
| Partner cabinet | `partner.garment-buro.ru` | Read-only partner identity, landing links, encrypted bank requisites, balance, payout requests, legal links, and support |
| Admin | `/admin/partners` | Partner onboarding, landing assembly, publishing, and model selection |
| Production | `/production` | Entry point to the existing protected production CRM |

## Catalog boundary

Catalog records are now internal garment models. They remain available to the constructor
and admin model selection, but the public catalog, presentation, and standalone product
pages are paused by `PUBLIC_CATALOG_ENABLED`.

## Landing templates

`partner_landings.template_key` selects the renderer. The initial `light-running` template
keeps the editorial, full screen storytelling of the LightRunning launch while all partner
copy, media, FAQs, and selected model identifiers come from validated landing data.

New templates must reuse the same landing, attribution, constructor, cart, order, and
commission contracts rather than introduce a separate checkout flow.
