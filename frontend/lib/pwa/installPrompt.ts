export type BeforeInstallPromptEvent = Event & {
    prompt: () => Promise<void>;
    userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>;
};

type PromptListener = (prompt: BeforeInstallPromptEvent | null) => void;

let retainedPrompt: BeforeInstallPromptEvent | null = null;
const listeners = new Set<PromptListener>();

export const getInstallPrompt = () => retainedPrompt;

export const retainInstallPrompt = (prompt: BeforeInstallPromptEvent) => {
    retainedPrompt = prompt;
    listeners.forEach(listener => listener(prompt));
};

export const clearInstallPrompt = () => {
    retainedPrompt = null;
    listeners.forEach(listener => listener(null));
};

export const subscribeToInstallPrompt = (listener: PromptListener) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
};
