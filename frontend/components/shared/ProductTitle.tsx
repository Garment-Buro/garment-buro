import { Fragment } from 'react';

import { splitProductTitle } from '@/lib/catalog/utils/catalog';

export const ProductTitle = ({ title }: { title: string }) => (
    <>
        {splitProductTitle(title).map((part, index) => (
            <Fragment key={`${part}-${index}`}>
                {index > 0 && <br />}
                {part}
            </Fragment>
        ))}
    </>
);
