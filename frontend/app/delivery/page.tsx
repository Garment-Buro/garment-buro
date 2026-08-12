import { TextPageContainer } from "@/components/shared/TextPageContainer";
import { Text } from "@/components/shared/Text";

export default function DeliveryPage() {
    return (
        <TextPageContainer>
            <Text as="h1" size={24} weight="bold" className="mb-10 text-center uppercase tracking-tight md:text-[32px]">
                Доставка
            </Text>
            <div className="space-y-6 text-[14px] leading-relaxed font-manrope">
                <p>
                    Мы осуществляем доставку по всей территории России. Мы сотрудничаем с ведущими курьерскими службами, такими как СДЭК, Почта России и Яндекс Маркет, чтобы обеспечить быструю и надежную доставку ваших заказов.
                </p>
                <p>
                    Стоимость и сроки доставки зависят от вашего региона и выбранного способа получения заказа. Вы сможете увидеть точную стоимость доставки при оформлении заказа.
                </p>
                <p>
                    После отправки заказа вы получите трек-номер для отслеживания посылки на указанный вами адрес электронной почты или в SMS.
                </p>
            </div>
        </TextPageContainer>
    );
}
