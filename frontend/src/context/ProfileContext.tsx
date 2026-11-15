import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';

const STORAGE_KEY = 's3a.farmer_profile.v1';

export interface ProfilePosition {
  latitude: number;
  longitude: number;
}

export interface FarmerProfile {
  displayName: string;
  village: string;
  position: ProfilePosition | null;
}

interface StoredProfile extends FarmerProfile {
  version: 1;
}

interface ProfileContextValue {
  profile: FarmerProfile | null;
  storageIssue: boolean;
  saveProfile: (profile: FarmerProfile) => boolean;
}

interface InitialProfileState {
  profile: FarmerProfile | null;
  storageIssue: boolean;
}

const ProfileContext = createContext<ProfileContextValue | null>(null);

function isPosition(value: unknown): value is ProfilePosition {
  if (typeof value !== 'object' || value === null) return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.latitude === 'number' &&
    Number.isFinite(record.latitude) &&
    record.latitude >= -90 &&
    record.latitude <= 90 &&
    typeof record.longitude === 'number' &&
    Number.isFinite(record.longitude) &&
    record.longitude >= -180 &&
    record.longitude <= 180
  );
}

function isStoredProfile(value: unknown): value is StoredProfile {
  if (typeof value !== 'object' || value === null) return false;
  const record = value as Record<string, unknown>;
  return (
    record.version === 1 &&
    typeof record.displayName === 'string' &&
    typeof record.village === 'string' &&
    (record.position === null || isPosition(record.position))
  );
}

function readStoredProfile(): InitialProfileState {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored) return { profile: null, storageIssue: false };

    const parsed: unknown = JSON.parse(stored);
    if (!isStoredProfile(parsed)) return { profile: null, storageIssue: true };

    return {
      profile: {
        displayName: parsed.displayName,
        village: parsed.village,
        position: parsed.position,
      },
      storageIssue: false,
    };
  } catch {
    return { profile: null, storageIssue: true };
  }
}

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [initial] = useState(readStoredProfile);
  const [profile, setProfile] = useState<FarmerProfile | null>(initial.profile);
  const [storageIssue, setStorageIssue] = useState(initial.storageIssue);

  const saveProfile = useCallback((next: FarmerProfile) => {
    const normalized: FarmerProfile = {
      displayName: next.displayName.trim(),
      village: next.village.trim(),
      position: isPosition(next.position) ? next.position : null,
    };
    setProfile(normalized);

    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, ...normalized }));
      setStorageIssue(false);
      return true;
    } catch {
      setStorageIssue(true);
      return false;
    }
  }, []);

  const value = useMemo(
    () => ({ profile, storageIssue, saveProfile }),
    [profile, storageIssue, saveProfile],
  );

  return <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>;
}

export function useProfile(): ProfileContextValue {
  const context = useContext(ProfileContext);
  if (!context) throw new Error('useProfile doit être utilisé dans <ProfileProvider>.');
  return context;
}
