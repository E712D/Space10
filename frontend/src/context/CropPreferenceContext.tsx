import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { usePlot } from './PlotContext';

const STORAGE_KEY = 's3a.crop_preferences.v1';
const EMPTY_CODES: string[] = [];

type PreferencesByPlot = Record<string, string[]>;

interface CropPreferenceContextValue {
  desiredCrops: string[];
  storageIssue: boolean;
  setDesiredCrops: (codes: string[]) => boolean;
}

interface InitialPreferences {
  preferences: PreferencesByPlot;
  storageIssue: boolean;
}

const CropPreferenceContext = createContext<CropPreferenceContextValue | null>(null);

function isPreferencesByPlot(value: unknown): value is PreferencesByPlot {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false;
  return Object.values(value).every(
    (codes) => Array.isArray(codes) && codes.every((code) => typeof code === 'string'),
  );
}

function readPreferences(): InitialPreferences {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored) return { preferences: {}, storageIssue: false };

    const parsed: unknown = JSON.parse(stored);
    if (!isPreferencesByPlot(parsed)) return { preferences: {}, storageIssue: true };
    return { preferences: parsed, storageIssue: false };
  } catch {
    return { preferences: {}, storageIssue: true };
  }
}

export function CropPreferenceProvider({ children }: { children: ReactNode }) {
  const { activePlot } = usePlot();
  const [initial] = useState(readPreferences);
  const [preferences, setPreferences] = useState(initial.preferences);
  const [storageIssue, setStorageIssue] = useState(initial.storageIssue);
  const plotId = activePlot?.plot_id ?? null;

  const setDesiredCrops = useCallback(
    (codes: string[]) => {
      if (!plotId) return false;
      const next = {
        ...preferences,
        [plotId]: [...new Set(codes.map((code) => code.trim()).filter(Boolean))],
      };
      setPreferences(next);

      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        setStorageIssue(false);
        return true;
      } catch {
        setStorageIssue(true);
        return false;
      }
    },
    [plotId, preferences],
  );

  const desiredCrops = plotId ? (preferences[plotId] ?? EMPTY_CODES) : EMPTY_CODES;
  const value = useMemo(
    () => ({ desiredCrops, storageIssue, setDesiredCrops }),
    [desiredCrops, storageIssue, setDesiredCrops],
  );

  return <CropPreferenceContext.Provider value={value}>{children}</CropPreferenceContext.Provider>;
}

export function useCropPreferences(): CropPreferenceContextValue {
  const context = useContext(CropPreferenceContext);
  if (!context) throw new Error('useCropPreferences doit être utilisé dans <CropPreferenceProvider>.');
  return context;
}
