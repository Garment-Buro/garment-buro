'use client';

import {useState} from 'react';

function AvatarImage({src, name, className, eager}: {src:string;name:string;className?:string;eager:boolean}) {
    const [failed,setFailed]=useState(false);
    if (failed) return <span className={className} role="img" aria-label={`Фото ${name} недоступно`}>{name.trim().slice(0,1).toLocaleUpperCase('ru')}</span>;
    // Direct API bytes preserve revocation; Next's image cache would retain published photos.
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt={name} width={512} height={512} className={className} loading={eager ? 'eager' : 'lazy'} onError={()=>setFailed(true)}/>;
}

export function PublicAvatar({src,name,className,eager=false}: {src:string|null;name:string;className?:string;eager?:boolean}) {
    return src ? <AvatarImage key={src} src={src} name={name} className={className} eager={eager}/>
        : <span className={className} role="img" aria-label={`Профиль ${name} без фото`}>{name.trim().slice(0,1).toLocaleUpperCase('ru')}</span>;
}
