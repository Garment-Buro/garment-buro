import { TextPageContainer } from "@/components/shared/TextPageContainer";
import { Text } from "@/components/shared/Text";

export default function ContactsPage() {
    return (
        <TextPageContainer>
            <Text as="h1" size={24} weight="bold" className="mb-10 text-center uppercase tracking-tight md:text-[32px]">
                Контакты
            </Text>
            <div className="space-y-6 text-[14px] leading-relaxed">
                <p>Email: tverfactory@gmail.com</p>
                <p>Адрес: Тверь, ул. 2-я Лукина, 9</p>
            </div>
        </TextPageContainer>
    );
}
