import { Popup } from '@/components/shared/Popup';
import { OrderContent } from '@/components/shared/OrderContent';

interface Props {
    params: Promise<{ id: string }>;
}

export default async function OrderModal({ params }: Props) {
    const { id } = await params;
    return (
        <Popup maxWidth={560}>
            <OrderContent orderId={id} />
        </Popup>
    );
}
