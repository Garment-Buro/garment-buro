'use client';

import {useState} from 'react';
import {usePeople} from '@/hooks/people/usePeople';
import {PageCursorExpiredError} from '@/lib/catalog/pagedResource';
import {ServiceCatalogIcon} from './ServiceCatalogIcon';
import {ServicePersonCard} from './ServicePersonCard';
import resultStyles from './ServiceSearchResults.module.css';
import styles from './ServiceCategoryCatalog.module.css';

export function ServicePeopleCatalog({query,onBack}:{query:string;onBack:()=>void}) {
    const [sort,setSort]=useState<'newest'|'name'>('newest');
    const people=usePeople({query,sort,limit:24});
    const cursorExpired=people.error instanceof PageCursorExpiredError ? people.error : null;
    return <section className={resultStyles.results} aria-labelledby="people-catalog-title">
        <div className={resultStyles.toolbar}>
            <button type="button" onClick={onBack} aria-label="Вернуться на главную"><ServiceCatalogIcon name="back" width={15} height={13}/></button>
            <h2 id="people-catalog-title">ЛЮДИ</h2>
            <select className={styles.sortSelect} aria-label="Порядок людей" value={sort} onChange={event=>setSort(event.target.value as 'newest'|'name')}>
                <option value="newest">Сначала новые</option><option value="name">По имени</option>
            </select>
        </div>
        <div className={resultStyles.scroller} role="group" tabIndex={0} aria-label="Каталог: люди" aria-busy={people.status==='loading' || people.loadingMore}>
            {people.status==='loading' || people.status==='idle' ? <p className={styles.status} role="status">Загружаем людей…</p>
                : people.status==='error' ? <p className={styles.status} role="alert">Не удалось загрузить людей. <button type="button" onClick={()=>{void people.retry()}}>Повторить</button></p>
                    : people.items.length ? <div className={styles.people}>{people.items.map(person=><ServicePersonCard key={person.id} person={person}/>)}</div>
                        : <p className={styles.status} role="status">Люди не найдены</p>}
            {people.status==='ready' && people.error!=null && <p className={styles.status} role="alert">{cursorExpired ? cursorExpired.message : 'Не удалось загрузить следующую страницу.'}</p>}
            {people.status==='ready' && people.nextCursor!==null && <button type="button" className={resultStyles.loadMore} disabled={people.loadingMore} onClick={()=>{void (cursorExpired ? people.retry() : people.loadMore())}}>{people.loadingMore ? 'Загружаем…' : cursorExpired ? 'Обновить список' : people.error!=null ? 'Повторить загрузку' : 'Показать ещё'}</button>}
        </div>
    </section>;
}
