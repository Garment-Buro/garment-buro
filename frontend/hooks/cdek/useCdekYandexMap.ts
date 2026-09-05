"use client";

import { useEffect, useMemo, useRef, useState } from 'react';

import type { CdekOffice, Coordinates, LoadState, YandexMapInstance, YandexMapsApi } from '@/lib/cdek/types';
import { getOfficeAddress, getOfficeCoords, getOfficeTitle } from '@/lib/cdek/utils/cdek';
import { loadYandexMaps } from '@/lib/cdek/utils/yandexMaps';

const escapeMapText = (value: string) => value.replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[character]!);

type UseCdekYandexMapOptions = {
    offices: CdekOffice[];
    selectedCode: string;
    searchCenter: Coordinates | null;
    selectedAddressLabel: string;
    onSelect: (code: string) => void;
};

export const useCdekYandexMap = ({
    offices,
    selectedCode,
    searchCenter,
    selectedAddressLabel,
    onSelect,
}: UseCdekYandexMapOptions) => {
    const mapNodeRef = useRef<HTMLDivElement | null>(null);
    const mapRef = useRef<YandexMapInstance | null>(null);
    const mapsApiRef = useRef<YandexMapsApi | null>(null);
    const [mapState, setMapState] = useState<LoadState>('loading');
    const officesWithCoords = useMemo(() => offices
        .map((office) => ({ office, coords: getOfficeCoords(office) }))
        .filter((item): item is { office: CdekOffice; coords: Coordinates } => Boolean(item.coords)), [offices]);

    useEffect(() => {
        let isMounted = true;

        loadYandexMaps().then((mapsApi) => {
            if (!isMounted || !mapNodeRef.current) return;
            mapsApiRef.current = mapsApi;
            mapRef.current ||= new mapsApi.Map(mapNodeRef.current, {
                center: officesWithCoords[0]?.coords || [55.7558, 37.6173],
                zoom: officesWithCoords.length > 1 ? 10 : 12,
                controls: ['zoomControl', 'fullscreenControl'],
            }, { suppressMapOpenBlock: true, yandexMapDisablePoiInteractivity: true });
            setMapState('ready');
        }).catch((error) => {
            console.warn('Yandex Maps failed:', error);
            if (isMounted) setMapState('error');
        });

        return () => { isMounted = false; };
    }, [officesWithCoords]);

    useEffect(() => {
        const map = mapRef.current;
        const mapsApi = mapsApiRef.current;
        if (!map || !mapsApi) return;

        map.geoObjects.removeAll();
        const bounds: number[][] = [];
        officesWithCoords.forEach(({ office, coords }) => {
            const isActive = office.code === selectedCode;
            const placemark = new mapsApi.Placemark(coords, {
                hintContent: escapeMapText(getOfficeTitle(office)),
                balloonContentHeader: escapeMapText(getOfficeTitle(office)),
                balloonContentBody: escapeMapText(getOfficeAddress(office)),
                balloonContentFooter: escapeMapText(office.work_time || ''),
            }, {
                preset: 'islands#circleIcon',
                iconColor: isActive ? '#D6FF58' : '#111111',
                hideIconOnBalloonOpen: false,
            });
            placemark.events.add('click', () => onSelect(office.code));
            map.geoObjects.add(placemark);
            bounds.push(coords);
        });

        if (searchCenter) {
            map.geoObjects.add(new mapsApi.Placemark(searchCenter, {
                hintContent: escapeMapText(selectedAddressLabel || 'Искомый адрес'),
                balloonContentHeader: 'Искомый адрес',
                balloonContentBody: escapeMapText(selectedAddressLabel),
            }, { preset: 'islands#redHomeIcon', iconColor: '#FF4D2D', zIndex: 1000 }));
        }

        const selected = officesWithCoords.find(({ office }) => office.code === selectedCode);
        if (selected) map.setCenter(selected.coords, 14, { duration: 250 });
        else if (searchCenter) map.setCenter(searchCenter, 13, { duration: 250 });
        else if (bounds.length > 1) map.setBounds([
            [Math.min(...bounds.map(point => point[0])), Math.min(...bounds.map(point => point[1]))],
            [Math.max(...bounds.map(point => point[0])), Math.max(...bounds.map(point => point[1]))],
        ], { checkZoomRange: true, zoomMargin: 36 });
        else if (bounds.length === 1) map.setCenter(bounds[0] as Coordinates, 13);
    }, [mapState, officesWithCoords, onSelect, searchCenter, selectedAddressLabel, selectedCode]);

    useEffect(() => () => {
        mapRef.current?.destroy();
        mapRef.current = null;
    }, []);

    return {
        mapNodeRef,
        mapState,
        officeCount: officesWithCoords.length,
    };
};
