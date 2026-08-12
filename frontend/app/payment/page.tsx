import { TextPageContainer } from "@/components/shared/TextPageContainer";
import { Text } from "@/components/shared/Text";

export default function PaymentPage() {
    return (
        <TextPageContainer>
            <Text as="h1" size={24} weight="bold" className="mb-10 text-center uppercase tracking-tight md:text-[32px]">
                Оплата и возврат
            </Text>
            <div className="space-y-6 text-[14px] leading-relaxed">
                <p>
                    Мы принимаем различные способы оплаты, включая банковские карты и электронные платежи.
                </p>
                <p>
                    Возврат товара осуществляется в соответствии с законодательством РФ в течение 14 дней с момента покупки,
                    при условии сохранения товарного вида и чека.
                </p>
            </div>
        </TextPageContainer>
    );
}
