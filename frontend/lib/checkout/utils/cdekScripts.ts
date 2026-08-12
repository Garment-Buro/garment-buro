import { loadScriptOnce } from '@/lib/browser/utils/scriptLoader';
import {
    CDEK_WIDGET_SCRIPT_ID,
    CDEK_WIDGET_SCRIPT_URL,
    YANDEX_MAPS_SCRIPT_ID,
    YANDEX_MAPS_SCRIPT_URL,
} from '@/lib/browser/config/vendorScripts';

export const loadCheckoutCdekScripts = async () => {
    if (!window.ymaps) await loadScriptOnce(YANDEX_MAPS_SCRIPT_ID, YANDEX_MAPS_SCRIPT_URL);
    if (!window.CDEKWidget) await loadScriptOnce(CDEK_WIDGET_SCRIPT_ID, CDEK_WIDGET_SCRIPT_URL);
};
