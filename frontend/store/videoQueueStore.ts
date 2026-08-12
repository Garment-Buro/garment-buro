import { create } from 'zustand';

type VideoStatus = 'idle' | 'loading' | 'loaded' | 'error';

interface QueuedVideo {
    id: string;
    priority: number;
    status: VideoStatus;
}

interface VideoQueueState {
    queue: Record<string, QueuedVideo>;
    logoLoaded: boolean;
    registerVideo: (id: string, priority: number) => void;
    unregisterVideo: (id: string) => void;
    setVideoStatus: (id: string, status: VideoStatus) => void;
}

export const useVideoQueue = create<VideoQueueState>((set) => ({
    queue: {},
    logoLoaded: false,

    registerVideo: (id, priority) => {
        set((state) => {
            if (state.queue[id]) return state; // Already registered
            return {
                queue: {
                    ...state.queue,
                    [id]: { id, priority, status: 'idle' }
                }
            };
        });
    },

    unregisterVideo: (id) => {
        set((state) => {
            if (!state.queue[id]) return state;
            const newQueue = { ...state.queue };
            delete newQueue[id];
            return { queue: newQueue };
        });
    },

    setVideoStatus: (id, status) => {
        set((state) => {
            if (!state.queue[id]) return state; // Safety check
            
            const newState = {
                queue: {
                    ...state.queue,
                    [id]: { ...state.queue[id], status }
                }
            };
            
            if (id === 'logo' && status === 'loaded') {
                return { ...newState, logoLoaded: true };
            }
            
            return newState;
        });
    }
}));

// Derived hook for a specific video component
export const useCanLoadVideo = (id: string) => {
    return useVideoQueue((state) => {
        if (id === 'logo') return true; // Logo always loads first
        const logo = state.queue.logo;
        if (!state.logoLoaded && logo?.status === 'loading') return false;
        
        const video = state.queue[id];
        if (!video) return false; // Not registered yet
        
        // If already loading or loaded, stay loadable
        if (video.status === 'loading' || video.status === 'loaded') return true;

        // If another video is already currently loading, wait
        const allVideos = Object.values(state.queue);
        const loadingVideos = allVideos.filter(v => v.id !== 'logo' && v.status === 'loading');
        
        // We allow 2 concurrent downloads maximum to utilize bandwidth well without stalling.  
        // Wait, for 3-7MB videos, 1 is safer, but 2 is fine on desktop. Let's do 1 concurrent to completely eliminate stutter.
        if (loadingVideos.length >= 1) return false;

        // Find the next eligible idle video
        const idleVideos = allVideos
            .filter(v => v.id !== 'logo' && v.status === 'idle')
            .sort((a, b) => {
                // lower number = higher priority
                if (a.priority === b.priority) {
                    return a.id.localeCompare(b.id);
                }
                return a.priority - b.priority;
            });

        // Is this video the absolute next in the queue?
        return idleVideos.length > 0 && idleVideos[0].id === id;
    });
};
