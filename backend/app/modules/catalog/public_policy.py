"""The same publication policy for storefront cards and customer favorites."""

from sqlalchemy import or_, select

from app.modules.catalog.models import Product, ProductCategory


def public_product_conditions():
    """Apply after an outer join to ProductCategory, retaining indexable product predicates."""
    return (
        Product.is_active.is_(True),
        Product.is_demo.is_(False),
        or_(Product.category_id.is_(None), ProductCategory.is_active.is_(True)),
    )


def public_product_ids():
    return (
        select(Product.id)
        .outerjoin(ProductCategory, Product.category_id == ProductCategory.id)
        .where(*public_product_conditions())
    )
