export const CART_ACTION_CONTENT_GLOW_COLLAPSED_HEIGHT = '300px';
export const CART_ACTION_CONTENT_GLOW_EXPANDED_HEIGHT = '100px';
export const CART_ACTION_CONTENT_GLOW_COLLAPSED_GRADIENT = 'radial-gradient(171.77% 41.81% at 50% 50%, rgba(255, 255, 255, 0.97) 38.95%, rgba(255, 255, 255, 0.79) 48.08%, rgba(255, 255, 255, 0.69) 53.37%, rgba(255, 255, 255, 0.50) 62.02%, rgba(255, 255, 255, 0.35) 69.24%, rgba(255, 255, 255, 0.20) 78.37%, rgba(255, 255, 255, 0.00) 97.12%)';
export const CART_ACTION_CONTENT_GLOW_EXPANDED_GRADIENT = 'radial-gradient(171.77% 41.81% at 50% 50%, rgba(255, 255, 255, 0.97) 38.95%, rgba(255, 255, 255, 0.79) 48.08%, rgba(255, 255, 255, 0.69) 53.37%, rgba(255, 255, 255, 0.50) 62.02%, rgba(255, 255, 255, 0.35) 69.24%, rgba(255, 255, 255, 0.20) 78.37%, rgba(255, 255, 255, 0.00) 97.12%)';

export const COLLAPSED_PRODUCT_MIN_HEIGHT = 49;
export const DRAG_START_THRESHOLD = 8;
export const DRAG_TAP_SLOP = 3;
export const DRAG_SNAP_MIN_DISTANCE = 96;
export const DRAG_SNAP_PROGRESS = 0.2;
export const CART_ACTION_BASE_VIEWPORT_WIDTH = 370;
export const CART_ACTION_MAX_VIEWPORT_WIDTH = 640;
export const CART_ACTION_EXPANDED_BASE_HEIGHT = 510;
export const CART_ACTION_EXPANDED_MIN_HEIGHT = 280;
export const CART_ACTION_EXPANDED_MAX_HEIGHT = 560;
export const CART_ACTION_EXPANDED_VIEWPORT_GAP = 80;
export const CART_ACTION_GUEST_AUTH_VIEWPORT_RESERVE = 105;
export const CART_ACTION_ENTER_MS = 420;
export const CART_ACTION_EXIT_MS = 340;
export const CART_ACTION_EXPAND_MS = 560;
export const CART_ACTION_REVEAL_MS = 420;
export const CART_ACTION_EXPANDED_BOTTOM_LIFT = 10;
export const CART_ACTION_SURFACE_REVEAL_START = 0.22;
export const CART_ACTION_SURFACE_REVEAL_RANGE = 0.48;
export const CART_ACTION_SURFACE_REVEAL_DELAY_MS = 150;
export const CART_ACTION_SURFACE_FADE_MS = 300;
export const CART_ACTION_CONTENT_REVEAL_START = 0.18;
export const CART_ACTION_CONTENT_REVEAL_RANGE = 0.46;
export const CART_ACTION_CONTENT_REVEAL_DELAY_MS = 120;
export const CART_ACTION_GUEST_AUTH_TOTAL_HEIGHT = 97;
export const HANDLE_CLICK_GUARD_MS = 450;
export const TOP_OVERSCROLL_COLLAPSE_THRESHOLD = 72;
export const WHEEL_GESTURE_RESET_MS = 160;
export const CART_ACTION_COURIER_DELIVERY_PRICE = 547;
export const CART_ACTION_COUPON_DISCOUNT = 540;
export const CART_ACTION_SURFACE_BACKGROUND = 'rgb(255 255 255 / 70%)';
export const CART_ACTION_SURFACE_BACKDROP_FILTER = 'blur(12px) saturate(160%)';
export const CART_ACTION_PRODUCT_SECTION_BACKGROUND = 'rgb(255 255 255 / 30%)';
export const CART_ACTION_SECTION_GAP_BACKGROUND = 'rgba(243, 243, 243, 0.7)';
export const CART_ACTION_COUPON_BUTTON_SHADOW = '0 0.665px 1.196px 0 rgba(0, 0, 0, 0.26)';

export const CART_ACTION_COUPONS = [
    { value: 'first-order', label: 'Первый заказ', amount: '10%' },
    { value: 'level-l', label: 'Уровень L', amount: '10%' },
    { value: 'ten-items', label: '10 изделий', amount: '10%' },
] as const;
