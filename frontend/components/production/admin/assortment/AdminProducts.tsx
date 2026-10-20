'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
    PiArrowLeft,
    PiArrowRight,
    PiImage,
    PiPackage,
    PiPencilSimple,
    PiPlus,
    PiTShirt,
    PiTrash,
    PiUsersThree,
} from 'react-icons/pi';
import { useAdminLandingDirectory } from '@/hooks/admin/useAdminLandingDirectory';
import type { AdminLandingCard } from '@/lib/partners/adminDirectory';
import { useProductionCatalog } from '@/hooks/production/useProductionCatalog';
import type { CatalogAdminCounts, CatalogAdminSort } from '@/lib/products/adminCatalog';
import { useAssortmentResource } from '@/hooks/production/useAssortmentResource';
import type {
    ProductReference,
} from '@/lib/production/assortmentTypes';
import { ProductEditorDialog } from '@/components/admin/ProductEditorDialog';
import { deleteProductionProduct } from '@/hooks/admin/catalogEditorClients';
import { safeImage } from '@/lib/production/workflow';
import { AdminFilters } from '../AdminFilters';
import { AssortmentDialog, AssortmentFeedback } from './AssortmentDialog';
import { CategoryDirectory, CategoryFilter } from './CategoryDirectory';
import { CategoryEditor } from './CategoryEditor';
import styles from '../ProductionAdmin.module.css';

const productPrice = (value: string | number) =>
    new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB',
        maximumFractionDigits: 2,
    }).format(Number(value));

export function AdminProducts({ initialProduct }: { initialProduct?: number | 'new' }) {
    const router = useRouter();
    const counts = useAssortmentResource<CatalogAdminCounts>('product-counts');
    const [search, setSearch] = useState('');
    const [categoryFilter, setCategoryFilter] = useState('');
    const [activityFilter, setActivityFilter] = useState('');
    const [stockFilter, setStockFilter] = useState('');
    const [sorting, setSorting] = useState<CatalogAdminSort>('title:asc');
    const [workspace, setWorkspace] = useState<'overview' | 'blanks' | 'communities' | 'users'>(
        initialProduct !== undefined ? 'blanks' : 'overview',
    );
    const [selectedCommunity, setSelectedCommunity] = useState<AdminLandingCard | null>(null);
    const [communitySearch, setCommunitySearch] = useState('');

    const communities = useAdminLandingDirectory('production', {query: communitySearch, limit:24}, workspace === 'communities' && selectedCommunity === null);
    const [editingId, setEditingId] = useState<number | 'new' | null>(initialProduct ?? null);
    const [deleting, setDeleting] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<ProductReference | null>(null);
    const [deleteError, setDeleteError] = useState('');
    const closeEditor = () => {
        setEditingId(null);
        if (initialProduct !== undefined) router.replace('/production?section=presets');
    };
    const [categoryTarget,setCategoryTarget] = useState<number|null|undefined>();
    const [categoryBusy,setCategoryBusy] = useState(false),[categoryRevision,setCategoryRevision] = useState(0);
    const [categoryFilterName,setCategoryFilterName] = useState('');
    const products = useProductionCatalog(
        {
            query: search.trim(),
            category_id: categoryFilter ? Number(categoryFilter) : undefined,
            active: activityFilter ? activityFilter === 'active' : undefined,
            stock: stockFilter === 'available' || stockFilter === 'empty' ? stockFilter : 'all',
            source: selectedCommunity ? 'all' : workspace === 'users' ? 'user' : 'garment_buro',
            community_id: selectedCommunity?.id,
            sort: sorting,
            limit: 24,
        },
        workspace === 'blanks' || workspace === 'users' || Boolean(selectedCommunity),
    );
    const visibleProducts = products.items;
    const editProduct = (reference: ProductReference) => setEditingId(reference.id);
    const removeProduct = async () => {
        if (!deleteTarget || deleting) return;
        setDeleting(true);
        setDeleteError('');
        try {
            await deleteProductionProduct(deleteTarget.id);
            setDeleteTarget(null);
            void products.retry();
            counts.reload();
        } catch (reason) {
            if (!(reason instanceof DOMException && reason.name === 'AbortError'))
                setDeleteError(reason instanceof Error ? reason.message : 'Не удалось удалить пресет.');
        } finally { setDeleting(false); }
    };
    return (
        <section aria-busy={products.loading || communities.loading}>
            <fieldset className={styles.adminFields} disabled={categoryBusy}>
            {workspace === 'overview' && (
                <>
                    <div className={styles.assortmentHeading}>
                        <div>
                            <h2>Пресеты</h2>
                            <p className={styles.muted}>
                                Бланки Garment Buro, пресеты лендингов и публикации пользователей.
                            </p>
                        </div>
                    </div>
                    <AssortmentFeedback
                        loading={counts.loading}
                        error={counts.error}
                        empty={false}
                    />
                    <div className={styles.catalogHub}>
                        <button
                            type="button"
                            className={styles.catalogHubCard}
                            onClick={() => setWorkspace('blanks')}
                        >
                            <span className={styles.catalogHubIcon}>
                                <PiTShirt aria-hidden />
                            </span>
                            <span>
                                <strong>Garment Buro</strong>
                                <small>Пресетов: {counts.data?.garment_buro ?? '…'}</small>
                            </span>
                            <PiArrowRight aria-hidden />
                        </button>
                        <button
                            type="button"
                            className={styles.catalogHubCard}
                            onClick={() => setWorkspace('communities')}
                        >
                            <span className={styles.catalogHubIcon}>
                                <PiUsersThree aria-hidden />
                            </span>
                            <span>
                                <strong>Пресеты по лендингам</strong>
                                <small>Лендингов: {counts.data?.communities ?? '…'}</small>
                            </span>
                            <PiArrowRight aria-hidden />
                        </button>
                        <button
                            type="button"
                            className={styles.catalogHubCard}
                            onClick={() => setWorkspace('users')}
                        >
                            <span className={styles.catalogHubIcon}>
                                <PiUsersThree aria-hidden />
                            </span>
                            <span>
                                <strong>Пресеты пользователей</strong>
                                <small>Пресетов: {counts.data?.user ?? '…'}</small>
                            </span>
                            <PiArrowRight aria-hidden />
                        </button>
                    </div>
                </>
            )}
            {workspace === 'communities' && !selectedCommunity && (
                <>
                    <div className={styles.assortmentHeading}>
                        <div>
                            <button
                                type="button"
                                className={styles.workspaceBack}
                                onClick={() => setWorkspace('overview')}
                            >
                                <PiArrowLeft aria-hidden /> Все пресеты
                            </button>
                            <h3>Пресеты по лендингам</h3>
                            <p className={styles.muted}>
                                Лендинги и пресеты, которые показываются в каждом из них.
                            </p>
                        </div>
                    </div>
                    <label className={styles.assortmentSearch}>
                        Поиск лендинга
                        <input type="search" value={communitySearch} onChange={event=>setCommunitySearch(event.target.value)} />
                    </label>
                    <AssortmentFeedback
                        loading={communities.loading}
                        error={communities.message}
                        empty={!communities.loading && communities.items.length === 0}
                    />
                    {communities.message && <button type="button" onClick={()=>void communities.retry()}>Обновить лендинги</button>}
                    <div className={styles.communityGrid}>
                        {communities.items.map((community) => {
                            const image = safeImage(community.image_url);
                            return (
                                <button
                                    type="button"
                                    className={styles.communityCard}
                                    key={community.id}
                                    onClick={() => setSelectedCommunity(community)}
                                >
                                    <span className={styles.communityMedia}>
                                        {image ? (
                                            // eslint-disable-next-line @next/next/no-img-element
                                            <img src={image} alt="" loading="lazy" />
                                        ) : (
                                            <PiUsersThree aria-hidden />
                                        )}
                                    </span>
                                    <span className={styles.communityBody}>
                                        <span>
                                            <small>{community.partner_name}</small>
                                            <strong>{community.title}</strong>
                                            <small>/{community.slug}</small>
                                        </span>
                                        <span>
                                            {community.product_count} пресетов
                                            <PiArrowRight aria-hidden />
                                        </span>
                                    </span>
                                </button>
                            );
                        })}
                    </div>
                    {communities.hasMore && <button type="button" disabled={communities.loadingMore} onClick={()=>void communities.loadMore()}>Ещё лендинги</button>}
                </>
            )}
            {(workspace === 'blanks' || workspace === 'users' || selectedCommunity) && (
                <>
                    <div className={styles.assortmentHeading}>
                        <div>
                            <button
                                type="button"
                                className={styles.workspaceBack}
                                onClick={() => {
                                    setSearch('');
                                    if (selectedCommunity) {
                                        setSelectedCommunity(null);
                                    } else {
                                        setWorkspace('overview');
                                    }
                                }}
                            >
                                <PiArrowLeft aria-hidden />
                                {selectedCommunity ? 'Пресеты по лендингам' : 'Все пресеты'}
                            </button>
                            <h3>
                                {selectedCommunity?.title ??
                                    (workspace === 'users'
                                        ? 'Пресеты пользователей'
                                        : 'Garment Buro')}
                            </h3>
                            <p className={styles.muted}>
                                {selectedCommunity
                                    ? `${selectedCommunity.partner_name} · /${selectedCommunity.slug}`
                                    : 'Пресеты, модели, теги и доступность по ткани.'}
                            </p>
                        </div>
                        {workspace === 'blanks' && (
                            <div className={styles.headingActions}>
                                <button
                                    onClick={() =>
                                        setCategoryTarget(null)
                                    }
                                >
                                    <PiPlus aria-hidden /> Категория каталога
                                </button>
                                <button
                                    onClick={() => {
                                        setEditingId('new');
                                    }}
                                >
                                    <PiPlus aria-hidden /> Добавить пресет
                                </button>
                            </div>
                        )}
                    </div>
                    {workspace==='blanks'&&<CategoryDirectory kind="product-categories" onEdit={setCategoryTarget} revision={categoryRevision}/>}
                    <div className={styles.assortmentFilters}>
                        <label className={styles.assortmentSearch}>
                            Поиск пресета
                            <input
                                type="search"
                                value={search}
                                placeholder="Название или адрес"
                                onChange={(event) => setSearch(event.target.value)}
                            />
                        </label>
                        <CategoryFilter revision={categoryRevision} kind="product-categories" value={Number(categoryFilter)||0} label={categoryFilterName} onChange={(id,name)=>{setCategoryFilter(id?String(id):'');setCategoryFilterName(name)}}/>
                        <AdminFilters
                            groups={[
                                {
                                    key: 'activity',
                                    label: 'Видимость',
                                    options: [
                                        ['', 'Все пресеты'],
                                        ['active', 'В продаже'],
                                        ['hidden', 'Скрытые'],
                                    ],
                                },
                                {
                                    key: 'stock',
                                    label: 'Остаток',
                                    options: [
                                        ['', 'Любой остаток'],
                                        ['available', 'Есть в наличии'],
                                        ['empty', 'Нет в наличии'],
                                    ],
                                },
                                {
                                    key: 'sorting',
                                    label: 'Сортировка',
                                    options: [
                                        ['title:asc', 'Название: А–Я'],
                                        ['title:desc', 'Название: Я–А'],
                                        ['price:asc', 'Сначала дешевле'],
                                        ['price:desc', 'Сначала дороже'],
                                        ['stock:desc', 'Больше остаток'],
                                        ['variants:desc', 'Больше вариантов'],
                                    ],
                                },
                            ]}
                            values={{
                                activity: activityFilter,
                                stock: stockFilter,
                                sorting,
                            }}
                            defaults={{
                                activity: '',
                                stock: '',
                                sorting: 'title:asc',
                            }}
                            onApply={(values) => {
                                setActivityFilter(values.activity);
                                setStockFilter(values.stock);
                                setSorting(values.sorting as CatalogAdminSort);
                            }}
                        />
                    </div>
                </>
            )}

            {(workspace === 'blanks' || workspace === 'users' || selectedCommunity) && (
                <AssortmentFeedback
                    loading={products.loading}
                    error={products.error}
                    empty={!products.loading && !products.error && visibleProducts.length === 0}
                />
            )}
            {products.error &&
                (workspace === 'blanks' || workspace === 'users' || selectedCommunity) && (
                    <button
                        type="button"
                        className={styles.button}
                        onClick={() => void products.retry()}
                    >
                        Обновить список
                    </button>
                )}
            {(workspace === 'blanks' || workspace === 'users' || selectedCommunity) && (
                <div className={styles.productGrid}>
                    {visibleProducts.map((product) => {
                        const image = safeImage(product.image_url);
                        const sku = product.sku;
                        const productCommunities = product.communities.map(community=>community.title);
                        const hiddenCommunities = (product.community_count ?? 0) - productCommunities.length;
                        return (
                            <article className={styles.productCard} key={product.id}>
                                <div className={styles.productMedia}>
                                    {image ? (
                                        // eslint-disable-next-line @next/next/no-img-element
                                        <img src={image} alt={product.title} loading="lazy" />
                                    ) : (
                                        <span className={styles.productMediaFallback}>
                                            <PiImage aria-hidden />
                                            <small>Нет фото</small>
                                        </span>
                                    )}
                                    <span
                                        className={styles.productStatus}
                                        data-active={product.is_active}
                                    >
                                        {product.is_active ? 'В продаже' : 'Скрыт'}
                                    </span>
                                </div>
                                <div className={styles.productCardBody}>
                                    <div className={styles.productCardHeader}>
                                        <div className={styles.productIdentity}>
                                            <span className={styles.productCategory}>
                                                {product.category_name ?? 'Без категории'}
                                            </span>
                                            <h4>{product.title}</h4>
                                            <small>
                                                {sku
                                                    ? `Артикул ${sku}`
                                                    : `/${product.slug ?? `product-${product.id}`}`}
                                            </small>
                                        </div>
                                        <button
                                            className={styles.iconButton}

                                            onClick={() => void editProduct(product)}
                                            aria-label={`Изменить пресет ${product.title}`}
                                            title="Изменить"
                                        >
                                            <PiPencilSimple aria-hidden />
                                        </button>
                                    </div>
                                    <button type="button" className={styles.button}
                                        aria-label={`Удалить пресет ${product.title}`}
                                        onClick={() => { setDeleteError(''); setDeleteTarget(product); }}>
                                        <PiTrash aria-hidden /> Удалить
                                    </button>
                                    <p className={styles.productModel}>
                                        <PiPackage aria-hidden />
                                        <span>
                                            {product.garment_model_name ?? 'Модель не назначена'}
                                        </span>
                                    </p>
                                    <p className={styles.productCommunity}>
                                        <PiUsersThree aria-hidden />
                                        <span>
                                            {product.community_count === null
                                                ? 'Нет данных о лендингах'
                                                : productCommunities.length
                                                ? `${productCommunities.join(', ')}${hiddenCommunities ? ` · ещё ${hiddenCommunities}` : ''}`
                                                : 'Без лендинга'}
                                        </span>
                                    </p>
                                    {Boolean(product.tags?.length) && (
                                        <p className={styles.muted}>{product.tags.join(' · ')}</p>
                                    )}
                                    <dl className={styles.productFacts}>
                                        <div>
                                            <dt>Цена</dt>
                                            <dd>{productPrice(product.price)}</dd>
                                        </div>
                                        <div>
                                            <dt>Доступно по ткани</dt>
                                            <dd>{product.stock_quantity} шт.</dd>
                                        </div>
                                        <div>
                                            <dt>Варианты</dt>
                                            <dd>{product.variant_count}</dd>
                                        </div>
                                    </dl>
                                </div>
                            </article>
                        );
                    })}
                </div>
            )}
            {products.hasMore &&
                (workspace === 'blanks' || workspace === 'users' || selectedCommunity) && (
                    <button
                        type="button"
                        className={styles.button}
                        disabled={products.loadingMore}
                        onClick={() => void products.loadMore()}
                    >
                        {products.loadingMore ? 'Загрузка…' : 'Загрузить ещё'}
                    </button>
                )}
            {deleteTarget && (
                <AssortmentDialog title="Удалить пресет" onClose={() => { if (!deleting) setDeleteTarget(null); }}>
                    <p>Удалить «{deleteTarget.title}»? Действие нельзя отменить. Для временного скрытия измените видимость товара.</p>
                    {deleteError && <p role="alert" className={styles.error}>{deleteError}</p>}
                    <div className={styles.editorActions}>
                        <button type="button" disabled={deleting} onClick={() => setDeleteTarget(null)}>Отмена</button>
                        <button type="button" className={styles.primaryButton} disabled={deleting} onClick={() => void removeProduct()}>
                            {deleting ? 'Удаляем…' : 'Удалить окончательно'}
                        </button>
                    </div>
                </AssortmentDialog>
            )}
            {categoryTarget!==undefined&&<CategoryEditor key={String(categoryTarget)} kind="product-categories" id={categoryTarget} onBusyChange={setCategoryBusy} onClose={()=>setCategoryTarget(undefined)} onSaved={()=>{setCategoryTarget(undefined);setCategoryRevision(value=>value+1);void products.retry()}}/>}
            {editingId !== null && (
                <ProductEditorDialog
                    key={editingId}
                    id={editingId === 'new' ? null : editingId}
                    onClose={closeEditor}
                    onSaved={() => {
                        closeEditor();
                        void products.retry();
                        counts.reload();
                    }}
                />
            )}
            </fieldset>
        </section>
    );
}
