"use client";

import { useCallback, useEffect, useMemo, useState } from 'react';
import { calculateCdekDelivery, getAddressSuggestions, getCdekOffices } from '@/lib/api/cdek';
import { CITY_PRESETS, DEMO_OFFICES, DEMO_TARIFF } from '@/lib/cdek/data';
import type { AddressSuggestion, CdekOffice, Coordinates, LoadState, TariffResult } from '@/lib/cdek/types';
import {
    filterCdekOffices,
    getAddressSuggestionLabel,
    sanitizeCdekCityCode,
} from '@/lib/cdek/utils/cdek';

export const useCdekTestPage = () => {
    const [cityCode, setCityCode] = useState(CITY_PRESETS[0].code);
    const [manualCityCode, setManualCityCode] = useState(String(CITY_PRESETS[0].code));
    const [query, setQuery] = useState('');
    const [offices, setOffices] = useState<CdekOffice[]>([]);
    const [selectedCode, setSelectedCode] = useState('');
    const [searchCenter, setSearchCenter] = useState<Coordinates | null>(null);
    const [selectedAddressLabel, setSelectedAddressLabel] = useState('');
    const [addressSuggestions, setAddressSuggestions] = useState<AddressSuggestion[]>([]);
    const [suggestState, setSuggestState] = useState<LoadState>('idle');
    const [loadState, setLoadState] = useState<LoadState>('idle');
    const [message, setMessage] = useState('Нажмите загрузку, чтобы получить ПВЗ через наш API-прокси.');
    const [isDemo, setIsDemo] = useState(false);
    const [tariff, setTariff] = useState<TariffResult | null>(null);
    const [tariffState, setTariffState] = useState<LoadState>('idle');

    const selectedOffice = useMemo(
        () => offices.find((office) => office.code === selectedCode) || null,
        [offices, selectedCode],
    );
    const filteredOffices = useMemo(
        () => filterCdekOffices(offices, query, searchCenter),
        [offices, query, searchCenter],
    );

    const resetSelection = useCallback(() => {
        setSelectedCode('');
        setSearchCenter(null);
        setSelectedAddressLabel('');
        setAddressSuggestions([]);
        setTariff(null);
        setTariffState('idle');
    }, []);

    const loadOffices = useCallback(async (nextCityCode: number) => {
        setLoadState('loading');
        setMessage('Загружаю пункты выдачи СДЭК...');
        resetSelection();
        setIsDemo(false);

        try {
            const nextOffices = await getCdekOffices(nextCityCode);
            setOffices(nextOffices);
            setLoadState('ready');
            setMessage(`Получили ${nextOffices.length} ПВЗ. Список идет из СДЭК через наш прокси, без официального виджета.`);
        } catch (error) {
            console.warn('Custom CDEK test fallback:', error);
            setOffices(DEMO_OFFICES);
            setLoadState('error');
            setIsDemo(true);
            setMessage('Не удалось получить реальные ПВЗ. Показываю демо-данные, чтобы можно было оценить кастомный UI.');
        }
    }, [resetSelection]);

    useEffect(() => {
        const search = query.trim();
        if (search.length < 3 || searchCenter) {
            return;
        }

        const controller = new AbortController();
        const timer = window.setTimeout(async () => {
            setSuggestState('loading');
            const cityLabel = CITY_PRESETS.find((city) => city.code === cityCode)?.label || '';
            try {
                const suggestions = await getAddressSuggestions(search, cityLabel, controller.signal);
                setAddressSuggestions((suggestions || []).slice(0, 6));
                setSuggestState('ready');
            } catch (error) {
                if (!controller.signal.aborted) {
                    console.warn('Address suggest failed:', error);
                    setAddressSuggestions([]);
                    setSuggestState('error');
                }
            }
        }, 280);

        return () => {
            controller.abort();
            window.clearTimeout(timer);
        };
    }, [cityCode, query, searchCenter]);

    useEffect(() => {
        const timer = window.setTimeout(() => void loadOffices(CITY_PRESETS[0].code), 0);
        return () => window.clearTimeout(timer);
    }, [loadOffices]);

    const selectCity = (nextCityCode: number) => {
        setCityCode(nextCityCode);
        setManualCityCode(String(nextCityCode));
        void loadOffices(nextCityCode);
    };

    const applyManualCityCode = () => {
        const parsedCode = Number(manualCityCode);
        if (!Number.isFinite(parsedCode) || parsedCode <= 0) {
            setMessage('Введите корректный числовой код города СДЭК.');
            return;
        }
        setCityCode(parsedCode);
        void loadOffices(parsedCode);
    };

    const changeQuery = (value: string) => {
        setQuery(value);
        setSuggestState('idle');
        resetSelection();
    };

    const selectSuggestion = (suggestion: AddressSuggestion) => {
        const label = getAddressSuggestionLabel(suggestion);
        if (!label) return;

        setQuery(label);
        setSelectedAddressLabel(label);
        setAddressSuggestions([]);
        setSelectedCode('');
        setTariff(null);
        setTariffState('idle');

        if (suggestion.coords) {
            setSearchCenter(suggestion.coords);
            setSuggestState('ready');
            setMessage(`Показываю ближайшие ПВЗ к адресу: ${label}`);
        } else {
            setSearchCenter(null);
            setSuggestState('error');
            setMessage('Не удалось определить координаты адреса. Можно выбрать ПВЗ из списка ниже.');
        }
    };

    const calculateTariff = async () => {
        if (!selectedOffice) return;
        if (isDemo) {
            setTariff(DEMO_TARIFF);
            setTariffState('ready');
            return;
        }

        setTariffState('loading');
        setTariff(null);
        try {
            setTariff(await calculateCdekDelivery(cityCode));
            setTariffState('ready');
        } catch (error) {
            console.warn('CDEK tariff failed:', error);
            setTariffState('error');
        }
    };

    return {
        cityCode,
        manualCityCode,
        query,
        offices,
        filteredOffices,
        selectedCode,
        selectedOffice,
        searchCenter,
        selectedAddressLabel,
        addressSuggestions,
        suggestState,
        loadState,
        message,
        isDemo,
        tariff,
        tariffState,
        setManualCityCode: (value: string) => setManualCityCode(sanitizeCdekCityCode(value)),
        setSelectedCode,
        selectCity,
        applyManualCityCode,
        changeQuery,
        selectSuggestion,
        calculateTariff,
    };
};

export type CdekTestController = ReturnType<typeof useCdekTestPage>;
