'use client';

import { useSyncExternalStore } from 'react';

const subscribe = () => () => undefined;
const getClientSnapshot = () => true;
const getServerSnapshot = () => false;

export const useClientReady = () => useSyncExternalStore(subscribe, getClientSnapshot, getServerSnapshot);
