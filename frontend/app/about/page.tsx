import { TextPageContainer } from "@/components/shared/TextPageContainer";
import { Text } from "@/components/shared/Text";

export default function AboutPage() {
    return (
        <TextPageContainer>
            <Text as="h1" size={24} weight="bold" className="mb-10 text-center uppercase tracking-tight md:text-[32px]">
                О нас
            </Text>
            <div className="space-y-6 text-[14px] leading-relaxed">
                <p>
                    Добро пожаловать в Garment Buro. Мы создаём качественные и стильные решения для вашего бизнеса.
                    Наша команда профессионалов всегда готова помочь вам в реализации самых смелых идей.
                </p>
                <p>
                    Мы верим в прозрачность, качество и индивидуальный подход к каждому клиенту.
                </p>
            </div>
        </TextPageContainer>
    );
}
