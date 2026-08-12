from __future__ import annotations

import json
import logging
import mimetypes
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import jwt
import redis
import uvicorn
from fastapi import FastAPI, File, HTTPException, Request, Security, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from markupsafe import Markup
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, create_engine, text
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqladmin import Admin, ModelView
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.exceptions import ConfigurationError
import email_service
from cdek_client import CdekClient
from image_optimization import optimize_image_bytes
from payments import YooKassaClient

mimetypes.add_type("image/webp", ".webp")

logger = logging.getLogger(__name__)
SETTINGS = get_settings()

DATABASE_URL = SETTINGS.legacy_database_url
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

security = HTTPBearer()

REDIS_URL = SETTINGS.redis_url
PRODUCTS_LIST_CACHE_TTL = SETTINGS.products_cache_ttl_seconds
PRODUCT_CACHE_TTL = SETTINGS.product_cache_ttl_seconds
CART_CACHE_TTL = SETTINGS.cart_cache_ttl_seconds
PRODUCTS_LIST_CACHE_KEY = "catalog:products:list"
PRODUCT_CACHE_PREFIX = "catalog:products:item:"
CART_CACHE_PREFIX = "cart:session:"
UPLOAD_CACHE_CONTROL = "public, max-age=31536000, immutable"

redis_client: Optional[redis.Redis] = None


def utc_now() -> datetime:
    """Return a naive UTC timestamp while the legacy SQLite schema is active."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

def init_redis_client():
    global redis_client
    if not REDIS_URL:
        redis_client = None
        logger.info("Redis cache is disabled")
        return
    try:
        client = redis.Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
            retry_on_timeout=True,
        )
        client.ping()
        redis_client = client
        logger.info("Redis cache connection established")
    except Exception:
        redis_client = None
        logger.warning("Redis is unavailable; continuing without cache")

def cache_get_json(key: str):
    if not redis_client:
        return None
    try:
        value = redis_client.get(key)
        return json.loads(value) if value else None
    except Exception:
        logger.warning("Redis cache read failed")
        return None

def cache_set_json(key: str, value, ttl_seconds: int):
    if not redis_client:
        return
    try:
        redis_client.setex(
            key,
            ttl_seconds,
            json.dumps(value, ensure_ascii=False, separators=(",", ":")),
        )
    except Exception:
        logger.warning("Redis cache write failed")

def invalidate_products_cache(product_ids: Optional[List[int]] = None):
    if not redis_client:
        return
    try:
        pipe = redis_client.pipeline()
        pipe.delete(PRODUCTS_LIST_CACHE_KEY)

        if product_ids:
            for pid in set(product_ids):
                pipe.delete(f"{PRODUCT_CACHE_PREFIX}{pid}")
        else:
            for key in redis_client.scan_iter(f"{PRODUCT_CACHE_PREFIX}*"):
                pipe.delete(key)

        pipe.execute()
    except Exception:
        logger.warning("Redis cache invalidation failed")


def sanitize_cart_id(cart_id: str) -> str:
    cart_id = (cart_id or "").strip()
    if not re.match(r"^[A-Za-z0-9_-]{8,128}$", cart_id):
        raise HTTPException(status_code=400, detail="Invalid cart id")
    return cart_id

# Models
class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    price = Column(Float)
    old_price = Column(Float, nullable=True)
    video_src = Column(String, nullable=True)
    image_left = Column(String, nullable=True)     # For mobile cards
    image_right = Column(String, nullable=True)    # For mobile cards
    description = Column(String, nullable=True)    # Multiline text
    composition = Column(String, nullable=True)    # Multiline text
    model_info = Column(String, nullable=True)     # Multiline text
    sizes = Column(String, nullable=True, default="S,M,L,XL") # Comma separated
    colors = Column(String, nullable=True, default="black,white") # Comma separated
    gallery_images = Column(String, nullable=True) # Comma separated URLs
    is_active = Column(Boolean, default=True)
    type = Column(String, default="normal")        # e.g., "худи" or just specific category
    
    # New fields
    weight = Column(Float, default=0.0)
    height = Column(Float, default=0.0)
    width = Column(Float, default=0.0)
    length = Column(Float, default=0.0)
    stock_quantity = Column(Integer, default=0)
    
    # Size Chart Photos
    size_chart_img_1 = Column(String, nullable=True)
    size_chart_img_2 = Column(String, nullable=True)
    
    # Desktop Assets
    desktop_video = Column(String, nullable=True)
    desktop_video_poster = Column(String, nullable=True) # Cover image shown before video loads
    desktop_card_images = Column(String, nullable=True) # Comma separated
    desktop_slider_images = Column(String, nullable=True) # Comma separated
    
    # Mobile Assets
    mobile_card_image = Column(String, nullable=True) # Photo on the left (Block 2)
    mobile_video_poster = Column(String, nullable=True) # Video cover/poster for mobile landing
    mobile_slider_images = Column(String, nullable=True)
    mobile_product_slider_images = Column(String, nullable=True)
    mobile_size_chart_first = Column(String, nullable=True) # First photo in mobile card on product page

    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")

class ProductVariant(Base):
    __tablename__ = "product_variants"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    size = Column(String, nullable=True)
    color = Column(String, nullable=True)
    color_hex = Column(String, nullable=True)       # e.g. '#1A1A1A'
    stock_quantity = Column(Integer, default=0)
    width_cm = Column(Float, nullable=True)         # Real garment width for this size
    height_cm = Column(Float, nullable=True)        # Real garment height/length for this size
    preview_image = Column(String, nullable=True)   # Main photo for variant picker
    images = Column(String, nullable=True)          # Comma-separated additional photos

    product = relationship("Product", back_populates="variants")

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    # Customer Info
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    patronymic = Column(String, nullable=True)
    # Delivery Info
    delivery_city = Column(String, nullable=True)
    delivery_method = Column(String, nullable=True)
    delivery_address = Column(String, nullable=True)
    # Payment Info
    payment_method = Column(String, nullable=True)
    # Cart Payload
    cart_items = Column(String, nullable=True)     # JSON string of items
    total_price = Column(Float, nullable=True)
    # Meta
    status = Column(String, default="new")         # new, processing, shipped, completed, cancelled
    cdek_uuid = Column(String, nullable=True)      # CDEK Order UUID
    cdek_point_code = Column(String, nullable=True) # CDEK pickup point code (for office delivery)
    delivery_price = Column(Float, nullable=True)   # Delivery cost from CDEK widget
    payment_id = Column(String, nullable=True)     # YooKassa Payment ID
    payment_status = Column(String, default="pending") # pending, paid, failed
    created_at = Column(DateTime, default=utc_now)
    cdek_number = Column(String, nullable=True)    # Human readable CDEK order number
    cdek_status = Column(String, nullable=True)    # CDEK status name

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    telegram_id = Column(String, unique=True, index=True, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    username = Column(String, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    
    # Profile info
    phone = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    birth_date = Column(String, nullable=True)
    height = Column(Float, nullable=True)
    weight = Column(Float, nullable=True)
    
    # Auth related
    otp_code = Column(String, nullable=True)
    otp_expiry = Column(DateTime, nullable=True)

# Pydantic schemata
class OrderCreate(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    patronymic: Optional[str] = None
    delivery_city: Optional[str] = None
    delivery_method: Optional[str] = None
    delivery_address: Optional[str] = None
    payment_method: Optional[str] = None
    cart_items: Optional[str] = None
    total_price: Optional[float] = None
    cdek_uuid: Optional[str] = None
    cdek_point_code: Optional[str] = None
    delivery_price: Optional[float] = None

class ProductVariantSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    size: Optional[str] = None
    color: Optional[str] = None
    color_hex: Optional[str] = None
    stock_quantity: int = 0
    width_cm: Optional[float] = None
    height_cm: Optional[float] = None
    preview_image: Optional[str] = None
    images: Optional[str] = None

class ProductCreate(BaseModel):
    title: str
    price: float
    old_price: Optional[float] = None
    video_src: Optional[str] = None
    image_left: Optional[str] = None
    image_right: Optional[str] = None
    description: Optional[str] = None
    composition: Optional[str] = None
    model_info: Optional[str] = None
    sizes: Optional[str] = "S,M,L,XL"
    colors: Optional[str] = "black,white"
    gallery_images: Optional[str] = None
    is_active: bool = True
    type: str = "normal"
    weight: Optional[float] = 0.0
    height: Optional[float] = 0.0
    width: Optional[float] = 0.0
    length: Optional[float] = 0.0
    stock_quantity: Optional[int] = 0
    size_chart_img_1: Optional[str] = None
    size_chart_img_2: Optional[str] = None
    desktop_video: Optional[str] = None
    desktop_video_poster: Optional[str] = None
    desktop_card_images: Optional[str] = None
    desktop_slider_images: Optional[str] = None
    mobile_card_image: Optional[str] = None
    mobile_video_poster: Optional[str] = None
    mobile_slider_images: Optional[str] = None
    mobile_product_slider_images: Optional[str] = None
    mobile_size_chart_first: Optional[str] = None
    variants: Optional[List[ProductVariantSchema]] = []


class CartItemSchema(BaseModel):
    id: str
    product_id: int
    title: str
    price: float
    image: str
    size: str
    color: str
    quantity: int


class CartUpsertPayload(BaseModel):
    items: List[CartItemSchema] = []
    updated_at_ms: Optional[int] = None

class AuthEmailRequest(BaseModel):
    email: str

class AuthVerifyRequest(BaseModel):
    email: str
    code: str

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    username: Optional[str]

# Helper functions
def get_jwt_secret() -> str:
    try:
        return SETTINGS.require_secret("jwt_secret", "JWT_SECRET")
    except ConfigurationError as error:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured",
        ) from error


def create_access_token(data: dict):
    to_encode = data.copy()
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    expire = utc_now() + timedelta(
        minutes=SETTINGS.jwt_access_expire_minutes
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        get_jwt_secret(),
        algorithm=SETTINGS.jwt_algorithm,
    )
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            get_jwt_secret(),
            algorithms=[SETTINGS.jwt_algorithm],
        )
        subject = payload.get("sub")
        if subject is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        try:
            user_id = int(subject)
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=401, detail="Invalid token") from error
        
        db = SessionLocal()
        user = db.query(User).filter(User.id == user_id).first()
        db.close()
        
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Create tables
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_redis_client()
    run_migrations()
    startup_event()
    yield


# FastAPI App
app = FastAPI(title=SETTINGS.app_name, lifespan=lifespan)

# Setup CORS to allow the Next.js frontend to talk to us
app.add_middleware(
    CORSMiddleware,
    allow_origins=SETTINGS.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)

yk_client = YooKassaClient()

def range_buffer_generator(file_path, start, chunk_size, size):
    with open(file_path, "rb") as f:
        f.seek(start)
        while size > 0:
            chunk = f.read(min(chunk_size, size))
            if not chunk:
                break
            size -= len(chunk)
            yield chunk

@app.get("/uploads/{filename}")
async def get_video(filename: str, request: Request):
    file_path = os.path.join("uploads", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    file_size = os.path.getsize(file_path)
    # Derive the correct Content-Type from the file extension. Hardcoding
    # "video/mp4" here breaks images on strict clients (iOS Safari refuses to
    # render an <img> served as video), while desktop browsers MIME-sniff and
    # still display them — which is why uploads loaded on desktop but not mobile.
    content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    range_header = request.headers.get("range")

    if range_header:
        start, end = range_header.replace("bytes=", "").split("-")
        start = int(start)
        end = int(end) if end else file_size - 1
        chunk_size = end - start + 1

        return StreamingResponse(
            range_buffer_generator(file_path, start, 1024*1024, chunk_size),
            status_code=206,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_size),
                "Content-Type": content_type,
                "Cache-Control": UPLOAD_CACHE_CONTROL,
                "X-Content-Type-Options": "nosniff",
            },
        )

    return StreamingResponse(
        open(file_path, "rb"),
        headers={
            "Content-Length": str(file_size),
            "Content-Type": content_type,
            "Cache-Control": UPLOAD_CACHE_CONTROL,
            "X-Content-Type-Options": "nosniff",
        },
    )

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Admin Panel Setup
def _normalize_media_url(raw: Optional[str]) -> str:
    if not raw:
        return ""
    url = raw.strip()
    if not url:
        return ""
    if url.startswith(("http://", "https://", "//", "data:", "blob:")):
        return url
    return url if url.startswith("/") else f"/{url}"


def _media_preview_html(raw: Optional[str]) -> Markup:
    if not raw:
        return Markup("")

    first = raw.split(",")[0].strip()
    url = _normalize_media_url(first)
    if not url:
        return Markup("")

    lower = url.lower()
    if lower.endswith((".mp4", ".webm", ".ogg", ".mov", ".m4v")):
        return Markup(
            f'<video src="{url}" style="width:120px;height:68px;object-fit:cover;border-radius:8px;" controls muted preload="metadata"></video>'
        )

    return Markup(
        f'<img src="{url}" style="width:68px;height:68px;object-fit:cover;border-radius:8px;" alt="preview" />'
    )


class ProductAdmin(ModelView, model=Product):
    column_list = [
        Product.id,
        Product.title,
        Product.price,
        Product.desktop_video,
        Product.desktop_video_poster,
        Product.mobile_card_image,
        Product.is_active,
    ]
    column_searchable_list = [Product.title]
    column_sortable_list = [Product.price]
    column_formatters = {
        Product.desktop_video: lambda m, a: _media_preview_html(m.desktop_video),
        Product.desktop_video_poster: lambda m, a: _media_preview_html(m.desktop_video_poster),
        Product.mobile_card_image: lambda m, a: _media_preview_html(m.mobile_card_image),
    }
    column_formatters_detail = column_formatters
    form_columns = [
        Product.title, 
        Product.price, 
        Product.old_price, 
        Product.video_src, 
        Product.image_left, 
        Product.image_right, 
        Product.description,
        Product.composition,
        Product.model_info,
        Product.sizes,
        Product.colors,
        Product.gallery_images,
        Product.is_active,
        Product.type,
        Product.weight,
        Product.height,
        Product.width,
        Product.length,
        Product.stock_quantity,
        Product.size_chart_img_1,
        Product.size_chart_img_2,
        Product.desktop_video,
        Product.desktop_card_images,
        Product.desktop_slider_images,
        Product.mobile_card_image,
        Product.mobile_slider_images,
        Product.mobile_product_slider_images,
        Product.mobile_size_chart_first
    ]

class OrderAdmin(ModelView, model=Order):
    column_list = [Order.id, Order.first_name, Order.phone, Order.total_price, Order.status, Order.cdek_uuid, Order.created_at]
    column_searchable_list = [Order.phone, Order.email, Order.last_name]
    column_sortable_list = [Order.created_at, Order.total_price]

class ProductVariantAdmin(ModelView, model=ProductVariant):
    column_list = [
        ProductVariant.id,
        ProductVariant.product_id,
        ProductVariant.size,
        ProductVariant.color,
        ProductVariant.width_cm,
        ProductVariant.height_cm,
        ProductVariant.stock_quantity,
        ProductVariant.preview_image,
    ]
    column_formatters = {
        ProductVariant.preview_image: lambda m, a: _media_preview_html(m.preview_image),
    }
    column_formatters_detail = column_formatters
    form_columns = [ProductVariant.product, ProductVariant.size, ProductVariant.color, ProductVariant.width_cm, ProductVariant.height_cm, ProductVariant.stock_quantity]

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.email, User.telegram_id, User.username, User.created_at]

admin = Admin(app, engine)
admin.add_view(ProductAdmin)
admin.add_view(OrderAdmin)
admin.add_view(ProductVariantAdmin)
admin.add_view(UserAdmin)

# Auto-migration: add new columns if missing
def run_migrations():
    migrations = [
        ("products", "desktop_video_poster", "TEXT"),
        ("products", "mobile_video_poster", "TEXT"),
        ("orders", "cdek_point_code", "TEXT"),
        ("orders", "delivery_price", "REAL"),
        ("orders", "cdek_number", "TEXT"),
        ("orders", "cdek_status", "TEXT"),
        ("products", "mobile_product_slider_images", "TEXT"),
        ("product_variants", "width_cm", "REAL"),
        ("product_variants", "height_cm", "REAL"),
    ]
    with engine.connect() as conn:
        for table, col, col_type in migrations:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                conn.commit()
                logger.info("Legacy migration added %s.%s", table, col)
            except Exception:
                pass  # Column already exists

# Mock Data Injection on Startup
def startup_event():
    db = SessionLocal()
    # Check if empty
    product_count = db.query(Product).count()
    if product_count == 0:
        logger.info("Legacy database is empty; injecting compatibility fixtures")
        mock_products = [
            Product(
                title='худи на молнии с мехом "Dark Normal"',
                price=5980,
                old_price=8490,
                video_src="/item_1.mp4",
                image_left="/landing-bg.png",
                image_right="/landing-bg.png"
            ),
            Product(
                title='худи на молнии с мехом "Night Слим"',
                price=5980,
                old_price=8490,
                video_src="/item_2.mp4",
                image_left="/landing-bg.png",
                image_right="/landing-bg.png"
            ),
            Product(
                title='худи на молнии с мехом "Cold Оверсайз"',
                price=5980,
                old_price=8490,
                video_src="/item_3.mp4",
                image_left="/landing-bg.png",
                image_right="/landing-bg.png"
            ),
            Product(
                title='худи на молнии с мехом "Cold Свободный"',
                price=5980,
                old_price=8490,
                video_src="/item_4.mp4",
                image_left="/landing-bg.png",
                image_right="/landing-bg.png"
            )
        ]
        db.add_all(mock_products)
        db.commit()
    db.close()

# API Endpoints
@app.get("/api/cart/{cart_id}")
def get_cart(cart_id: str):
    safe_cart_id = sanitize_cart_id(cart_id)
    key = f"{CART_CACHE_PREFIX}{safe_cart_id}"
    cached = cache_get_json(key)

    if isinstance(cached, dict):
        return {
            "cart_id": safe_cart_id,
            "items": cached.get("items", []),
            "updated_at_ms": int(cached.get("updated_at_ms") or 0),
            "ttl_seconds": CART_CACHE_TTL,
        }

    return {
        "cart_id": safe_cart_id,
        "items": [],
        "updated_at_ms": 0,
        "ttl_seconds": CART_CACHE_TTL,
    }


@app.put("/api/cart/{cart_id}")
def upsert_cart(cart_id: str, payload: CartUpsertPayload):
    safe_cart_id = sanitize_cart_id(cart_id)
    key = f"{CART_CACHE_PREFIX}{safe_cart_id}"
    updated_at_ms = payload.updated_at_ms if (payload.updated_at_ms and payload.updated_at_ms > 0) else int(utc_now().timestamp() * 1000)
    body = {
        "items": [item.model_dump() for item in payload.items],
        "updated_at_ms": updated_at_ms,
    }
    cache_set_json(key, body, CART_CACHE_TTL)
    return {
        "status": "ok",
        "cart_id": safe_cart_id,
        "items_count": len(body["items"]),
        "updated_at_ms": updated_at_ms,
        "ttl_seconds": CART_CACHE_TTL,
    }


@app.delete("/api/cart/{cart_id}")
def delete_cart(cart_id: str):
    safe_cart_id = sanitize_cart_id(cart_id)
    key = f"{CART_CACHE_PREFIX}{safe_cart_id}"
    if redis_client:
        try:
            redis_client.delete(key)
        except Exception:
            logger.warning("Redis cart deletion failed")
    return {"status": "deleted", "cart_id": safe_cart_id}


@app.get("/api/products")
def get_products():
    cached = cache_get_json(PRODUCTS_LIST_CACHE_KEY)
    if cached is not None:
        return cached

    db = SessionLocal()
    try:
        products = db.query(Product).order_by(Product.id.desc()).all()
        payload = jsonable_encoder(products)
        cache_set_json(PRODUCTS_LIST_CACHE_KEY, payload, PRODUCTS_LIST_CACHE_TTL)
        return payload
    finally:
        db.close()

@app.get("/api/products/{product_id}")
def get_product(product_id: int):
    cache_key = f"{PRODUCT_CACHE_PREFIX}{product_id}"
    cached = cache_get_json(cache_key)
    if cached is not None:
        return cached

    db = SessionLocal()
    try:
        from sqlalchemy.orm import joinedload
        product = db.query(Product).options(joinedload(Product.variants)).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        payload = jsonable_encoder(product)
        cache_set_json(cache_key, payload, PRODUCT_CACHE_TTL)
        return payload
    finally:
        db.close()

@app.post("/api/products")
def create_product(product_data: ProductCreate):
    db = SessionLocal()
    try:
        data = product_data.model_dump()
        variants_data = data.pop("variants", [])
        
        new_product = Product(**data)
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
        
        for v in variants_data:
            new_variant = ProductVariant(product_id=new_product.id, **v)
            db.add(new_variant)
        
        db.commit()
        db.refresh(new_product)
        payload = jsonable_encoder(new_product)
        invalidate_products_cache([new_product.id])
        return payload
    finally:
        db.close()

@app.put("/api/products/{product_id}")
def update_product(product_id: int, product_data: ProductCreate):
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        data = product_data.model_dump()
        variants_data = data.pop("variants", [])
        
        for key, value in data.items():
            setattr(product, key, value)
        
        # Update variants
        # Simple strategy: delete existing and recreate
        db.query(ProductVariant).filter(ProductVariant.product_id == product_id).delete()
        for v in variants_data:
            v.pop('id', None) 
            new_variant = ProductVariant(product_id=product.id, **v)
            db.add(new_variant)
        
        db.commit()
        # Explicitly load variants for the response
        from sqlalchemy.orm import joinedload
        product = db.query(Product).options(joinedload(Product.variants)).filter(Product.id == product_id).first()
        payload = jsonable_encoder(product)
        invalidate_products_cache([product_id])
        return payload
    finally:
        db.close()

@app.delete("/api/products/{product_id}")
def delete_product(product_id: int):
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        db.delete(product)
        db.commit()
        invalidate_products_cache([product_id])
        return {"status": "deleted"}
    finally:
        db.close()

@app.post("/api/auth/email/request")
def request_otp(req: AuthEmailRequest):
    db = SessionLocal()
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        user = User(email=req.email)
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # Generate 4-digit code
    code = "".join([str(secrets.randbelow(10)) for _ in range(4)])
    user.otp_code = code
    user.otp_expiry = utc_now() + timedelta(minutes=10)
    db.commit()
    db.close()
    # In a real app, send email here. Now implemented!
    email_service.send_auth_otp(req.email, code)
    
    return {"status": "sent", "testing_only_otp": code}

@app.post("/api/auth/email/verify")
def verify_otp(req: AuthVerifyRequest):
    db = SessionLocal()
    user = db.query(User).filter(User.email == req.email).first()
    if not user or user.otp_code != req.code:
        db.close()
        raise HTTPException(status_code=400, detail="Invalid code")
    
    if user.otp_expiry < utc_now():
        db.close()
        raise HTTPException(status_code=400, detail="Code expired")
    
    # Clear OTP
    user.otp_code = None
    user.otp_expiry = None
    db.commit()
    
    token = create_access_token({"sub": user.id})
    db.close()
    
    return {"token": token, "user": {"id": user.id, "email": user.email}}

@app.get("/api/auth/me")
async def get_me(user: User = Security(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "phone": user.phone,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "gender": user.gender,
        "birth_date": user.birth_date,
        "height": user.height,
        "weight": user.weight,
        "created_at": user.created_at
    }

@app.put("/api/auth/me")
async def update_me(data: dict, user: User = Security(get_current_user)):
    db = SessionLocal()
    db_user = db.query(User).filter(User.id == user.id).first()
    
    for key in ["first_name", "last_name", "gender", "birth_date", "height", "weight", "phone"]:
        if key in data:
            setattr(db_user, key, data[key])
    
    db.commit()
    db.refresh(db_user)
    db.close()
    return db_user

@app.post("/api/auth/me/email/request")
def request_email_link_otp(req: AuthEmailRequest, user: User = Security(get_current_user)):
    db = SessionLocal()
    existing = db.query(User).filter(User.email == req.email, User.id != user.id).first()
    if existing:
        db.close()
        raise HTTPException(status_code=400, detail="Этот email уже используется другим аккаунтом")
        
    db_user = db.query(User).filter(User.id == user.id).first()
    code = "".join([str(secrets.randbelow(10)) for _ in range(4)])
    db_user.otp_code = code
    db_user.otp_expiry = utc_now() + timedelta(minutes=10)
    db.commit()
    db.close()
    
    import email_service
    email_service.send_auth_otp(req.email, code)
    return {"status": "sent", "testing_only_otp": code}

@app.post("/api/auth/me/email/verify")
def verify_email_link_otp(req: AuthVerifyRequest, user: User = Security(get_current_user)):
    db = SessionLocal()
    db_user = db.query(User).filter(User.id == user.id).first()
    
    if not db_user or db_user.otp_code != req.code:
        db.close()
        raise HTTPException(status_code=400, detail="Неверный код")
        
    if db_user.otp_expiry and db_user.otp_expiry < utc_now():
        db.close()
        raise HTTPException(status_code=400, detail="Код истёк")
        
    db_user.email = req.email
    db_user.otp_code = None
    db_user.otp_expiry = None
    db.commit()
    db.refresh(db_user)
    db.close()
    return db_user

@app.delete("/api/auth/me")
async def delete_me(user: User = Security(get_current_user)):
    db = SessionLocal()
    db_user = db.query(User).filter(User.id == user.id).first()
    db.delete(db_user)
    db.commit()
    db.close()
    return {"status": "deleted"}

from sqlalchemy import or_

@app.get("/api/auth/orders")
async def get_my_orders(user: User = Security(get_current_user)):
    db = SessionLocal()
    conditions = []
    if user.email:
        conditions.append(Order.email == user.email)
    if user.phone:
        conditions.append(Order.phone == user.phone)
        
    if not conditions:
        db.close()
        return []

    orders = db.query(Order).filter(or_(*conditions)).order_by(Order.id.desc()).all()
    
    # Update CDEK statuses
    client = CdekClient()
    for order in orders:
        if order.cdek_uuid:
            try:
                status_code, cdek_data = await client.get_order_info(order.cdek_uuid)
                if status_code == 200:
                    entity = cdek_data.get("entity", {})
                    cdek_number = entity.get("cdek_number")
                    
                    statuses = entity.get("statuses", [])
                    cdek_status = None
                    if statuses:
                        # They are usually sorted chronologically, check CDEK docs, the last one is actual? Wait, code could be something else. Usually statuses[0] or statuses[-1]
                        cdek_status = statuses[-1].get("name")
                    
                    updated = False
                    if cdek_number and order.cdek_number != cdek_number:
                        order.cdek_number = cdek_number
                        updated = True
                    if cdek_status and order.cdek_status != cdek_status:
                        order.cdek_status = cdek_status
                        updated = True
                        
                    if updated:
                        db.commit()
            except Exception:
                logger.warning("Unable to refresh CDEK status for an order")
                
    # Also attach the status so the frontend gets it immediately inside JSON
    result = []
    for order in orders:
        order_dict = {col.name: getattr(order, col.name) for col in order.__table__.columns}
        result.append(order_dict)

    db.close()
    return result

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    original_filename = file.filename or "upload"
    ext = Path(original_filename).suffix.lower() or ".bin"
    data = await file.read()

    if ext in {".png", ".jpg", ".jpeg"}:
        optimized = await run_in_threadpool(optimize_image_bytes, data)
        if optimized is not None:
            data = optimized
            ext = ".webp"

    filename = f"{secrets.token_urlsafe(8)}{ext}"
    filepath = os.path.join("uploads", filename)

    with open(filepath, "wb") as f:
        f.write(data)

    return {"url": f"/uploads/{filename}"}

@app.post("/api/orders")
async def create_order(order_data: OrderCreate):
    db = SessionLocal()
    new_order = Order(**order_data.model_dump())
    changed_product_ids = set()
    
    # Decrement stock
    if new_order.cart_items:
        try:
            import json
            items = json.loads(new_order.cart_items)
            for item in items:
                prod_id = item.get('product_id')
                qty = item.get('quantity', 1)
                size = item.get('size')
                color = item.get('color')
                
                if prod_id:
                    changed_product_ids.add(int(prod_id))
                    # Update global stock
                    product = db.query(Product).filter(Product.id == prod_id).first()
                    if product:
                        product.stock_quantity = max(0, product.stock_quantity - qty)
                        
                        # Update variant stock if size/color provided
                        if size or color:
                            variant = db.query(ProductVariant).filter(
                                ProductVariant.product_id == prod_id,
                                ProductVariant.size == size,
                                ProductVariant.color == color
                            ).first()
                            if variant:
                                variant.stock_quantity = max(0, variant.stock_quantity - qty)
        except Exception:
            logger.warning("Unable to update legacy stock counters")

    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    # Handle YooKassa Payment
    payment_url = None
    if order_data.payment_method in ['card', 'qr']:
        try:
            db.refresh(new_order)
            title_summary = "Заказ предметов Garment Buro"
            if new_order.cart_items:
                import json
                items = json.loads(new_order.cart_items)
                if items:
                    title_summary = items[0].get('title', title_summary)
                    if len(items) > 1:
                        title_summary += f" и еще {len(items)-1}"

            return_url = (
                f"{SETTINGS.public_base_url.rstrip('/')}/order/{new_order.id}"
            )
            
            yk_payment_method = "sbp" if order_data.payment_method == 'qr' else "bank_card"

            pay_url, pay_id = yk_client.create_payment(
                amount=new_order.total_price or 0.0,
                description=title_summary,
                order_id=new_order.id,
                email=new_order.email or "",
                return_url=return_url,
                payment_method=yk_payment_method
            )

            new_order.payment_id = pay_id
            db.commit()
            payment_url = pay_url
        except Exception:
            logger.warning("YooKassa payment creation failed")
    else:
        # For non-card payments register CDEK immediately (card payments register after webhook)
        if new_order.delivery_method and ("cdek" in new_order.delivery_method.lower() or "сдэк" in new_order.delivery_method.lower()):
            try:
                client = CdekClient()
                cdek_uuid = await client.register_order(new_order)
                if cdek_uuid:
                    new_order.cdek_uuid = cdek_uuid
                    db.commit()
            except Exception:
                logger.warning("CDEK order registration failed")
        
    res_order_id = new_order.id
    res_cdek_uuid = new_order.cdek_uuid
    if changed_product_ids:
        invalidate_products_cache(list(changed_product_ids))
    db.close()
    return {
        "status": "success", 
        "order_id": res_order_id, 
        "cdek_uuid": res_cdek_uuid, 
        "payment_url": payment_url
    }

@app.post("/api/webhooks/yookassa")
async def yookassa_webhook(request: Request):
    db = SessionLocal()
    try:
        data = await request.json()
        event = data.get("event")
        obj = data.get("object", {})
        payment_id = obj.get("id")
        
        if event == "payment.succeeded":
            order = db.query(Order).filter(Order.payment_id == payment_id).first()
            if order:
                order.payment_status = "paid"
                order.status = "processing"
                db.commit()
                
                # After payment, register for CDEK
                if order.delivery_method and ("cdek" in order.delivery_method.lower() or "сдэк" in order.delivery_method.lower()):
                    try:
                        client = CdekClient()
                        cdek_uuid = await client.register_order(order)
                        if cdek_uuid:
                            order.cdek_uuid = cdek_uuid
                            db.commit()
                    except Exception:
                        logger.warning("CDEK registration after payment failed")
                
                # After payment, send confirmation email
                email_service.send_order_confirmation(order)
    except Exception:
        logger.warning("YooKassa webhook processing failed")
    finally:
        db.close()
    
    return {"status": "ok"}

@app.get("/api/orders")
def get_orders():
    db = SessionLocal()
    orders = db.query(Order).order_by(Order.id.desc()).all()
    db.close()
    return orders

@app.get("/api/orders/{order_id}")
def get_order(order_id: int):
    db = SessionLocal()
    order = db.query(Order).filter(Order.id == order_id).first()
    db.close()
    if not order:
        return {"error": "Order not found"}, 404
    return order

# Variant endpoints
@app.get("/api/products/{product_id}/variants")
def get_variants(product_id: int):
    db = SessionLocal()
    variants = db.query(ProductVariant).filter(ProductVariant.product_id == product_id).all()
    db.close()
    return variants

@app.put("/api/variants/{variant_id}")
def update_variant(variant_id: int, data: ProductVariantSchema):
    db = SessionLocal()
    variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
    if not variant:
        db.close()
        raise HTTPException(status_code=404, detail="Variant not found")
    for key, value in data.model_dump(exclude={"id"}).items():
        setattr(variant, key, value)
    db.commit()
    db.refresh(variant)
    invalidate_products_cache([variant.product_id])
    db.close()
    return variant

# Color/Size Options endpoints
OPTIONS_FILE = "uploads/variant_options.json"
SETTINGS_FILE = "uploads/settings.json"

def get_default_options():
    return {
        "colors": [
            {"label": "Черный", "hex": "#1A1A1A"},
            {"label": "Белый", "hex": "#FFFFFF"},
        ],
        "sizes": ["XS", "S", "M", "L", "XL", "XXL"]
    }

@app.get("/api/options")
def get_options():
    if not os.path.exists(OPTIONS_FILE):
        return get_default_options()
    try:
        with open(OPTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return get_default_options()

@app.put("/api/options")
def update_options(options: dict):
    with open(OPTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(options, f, ensure_ascii=False, indent=2)
    return options


def get_default_settings():
    return {
        "logo_video_url": "/logo_anim.mp4",
        "hero_products": [1, 2, 3, 4],
        "showroom1_products": [2, 3, 4],
        "showroom2_products": [1, 2, 3, 4],
        "links": {}
    }

@app.get("/api/settings")
def get_settings():
    if not os.path.exists(SETTINGS_FILE):
        return get_default_settings()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return get_default_settings()

@app.put("/api/settings")
def update_settings(settings: dict):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    return settings

@app.post("/api/cdek/calculate")
async def calculate_cdek_tariff(request: Request):
    try:
        body = await request.json()
        city = body.get("city")
        delivery_method = body.get("delivery_method")
        cart_items = body.get("cart_items", [])
        
        from cdek_client import CdekClient
        client = CdekClient()
        city_code = await client.get_city_code(city)
        if not city_code:
            return {"delivery_price": 0}
            
        packages = []
        for item in cart_items:
            packages.append({
                "weight": int(item.get("weight", 500)),
                "length": int(item.get("length", 20)),
                "width": int(item.get("width", 20)),
                "height": int(item.get("height", 10)),
            })
            
        if not packages:
            packages = [{"weight": 1000, "length": 20, "width": 20, "height": 10}]
            
        tariff_code = (
            client.warehouse_to_door_tariff
            if delivery_method == "cdek_door"
            else client.warehouse_to_warehouse_tariff
        )
        result = await client.calculate_tariffs_by_code(
            client.sender_city_code,
            city_code,
            tariff_code,
            packages,
        )
        
        if result and result.get("delivery_sum"):
            return {"delivery_price": result.get("delivery_sum")}
        return {"delivery_price": 0}
    except Exception:
        logger.warning("CDEK tariff calculation failed")
        return {"delivery_price": 0}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
