import { TextPageContainer } from "@/components/shared/TextPageContainer";
import { Text } from "@/components/shared/Text";

export default function DevPage() {
    return (
        <TextPageContainer>
            <Text as="h1" size={24} weight="bold" className="mb-10 text-center uppercase tracking-tight md:text-[32px]">
                Разработка
            </Text>
            <div className="space-y-6 text-[14px] leading-relaxed">
                <p>Раздел в разработке.</p>
            </div>
        </TextPageContainer>
    );
}
