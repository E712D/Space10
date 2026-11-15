import { CheckCircle2, Loader2, MapPin, UserRound } from 'lucide-react';
import { useRef, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router';
import { Button, ButtonLink } from '../components/Button';
import { ScreenHeader } from '../components/ScreenHeader';
import { useProfile, type ProfilePosition } from '../context/ProfileContext';
import { fr } from '../i18n/fr';

const t = fr.profile;
const GEO_TIMEOUT_MS = 10_000;

export function ProfilePage() {
  const navigate = useNavigate();
  const { profile, storageIssue, saveProfile } = useProfile();
  const [displayName, setDisplayName] = useState(profile?.displayName ?? '');
  const [village, setVillage] = useState(profile?.village ?? '');
  const [position, setPosition] = useState<ProfilePosition | null>(profile?.position ?? null);
  const [nameError, setNameError] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);
  const nameInput = useRef<HTMLInputElement>(null);

  const locate = () => {
    if (!('geolocation' in navigator)) {
      setLocationError(t.location_unsupported);
      return;
    }

    setLocating(true);
    setLocationError(null);
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setPosition({
          latitude: Number(coords.latitude.toFixed(4)),
          longitude: Number(coords.longitude.toFixed(4)),
        });
        setLocating(false);
      },
      (error) => {
        const message =
          error.code === error.PERMISSION_DENIED
            ? t.location_denied
            : error.code === error.POSITION_UNAVAILABLE
              ? t.location_unavailable
              : error.code === error.TIMEOUT
                ? t.location_timeout
                : t.location_error;
        setLocationError(message);
        setLocating(false);
      },
      { timeout: GEO_TIMEOUT_MS, maximumAge: 60_000 },
    );
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const name = displayName.trim();
    if (!name) {
      setNameError(true);
      nameInput.current?.focus();
      return;
    }

    setNameError(false);
    saveProfile({ displayName: name, village, position });
    navigate('/', { replace: true });
  };

  return (
    <main className="flex-1 pb-8">
      <ScreenHeader
        eyebrow={t.eyebrow}
        title={t.title}
        action={profile ? <ButtonLink to="/" variant="ghost" size="default">{t.cancel}</ButtonLink> : undefined}
      />

      <form className="mx-5 mt-3 space-y-4" onSubmit={submit}>
        <p className="text-sm leading-relaxed text-muted-foreground">{t.intro}</p>

        {storageIssue && (
          <p role="status" className="rounded-2xl bg-warning-soft p-3 text-sm font-medium text-foreground">
            {t.storage_issue}
          </p>
        )}

        <section className="space-y-4 rounded-3xl bg-card p-4 shadow-card">
          <label className="block text-sm font-bold" htmlFor="profile-name">
            <span className="flex items-center gap-2">
              <UserRound className="size-4 text-primary" aria-hidden="true" />
              {t.name_label}
            </span>
            <input
              id="profile-name"
              name="name"
              autoComplete="name"
              ref={nameInput}
              maxLength={60}
              aria-required="true"
              value={displayName}
              onChange={(event) => {
                setDisplayName(event.target.value);
                if (event.target.value.trim()) setNameError(false);
              }}
              aria-invalid={nameError}
              aria-describedby={nameError ? 'profile-name-error' : undefined}
              placeholder={t.name_placeholder}
              className="mt-2 h-14 w-full rounded-2xl border-2 border-border bg-background px-4 text-base font-semibold outline-none transition focus:border-leaf"
            />
            {nameError && (
              <span id="profile-name-error" role="alert" className="mt-1 block text-sm font-medium text-destructive">
                {t.name_required}
              </span>
            )}
          </label>

          <label className="block text-sm font-bold" htmlFor="profile-village">
            {t.village_label}
            <input
              id="profile-village"
              name="village"
              autoComplete="address-level2"
              maxLength={80}
              value={village}
              onChange={(event) => setVillage(event.target.value)}
              placeholder={t.village_placeholder}
              className="mt-2 h-14 w-full rounded-2xl border-2 border-border bg-background px-4 text-base font-semibold outline-none transition focus:border-leaf"
            />
          </label>
        </section>

        <section className="rounded-3xl bg-card p-4 shadow-soft">
          <h2 className="flex items-center gap-2 font-bold">
            <MapPin className="size-5 text-primary" aria-hidden="true" />
            {t.location_title}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{t.location_text}</p>
          <Button
            type="button"
            variant="outline"
            className="mt-3 w-full"
            disabled={locating}
            aria-busy={locating}
            onClick={locate}
          >
            {locating ? <Loader2 className="animate-spin" /> : <MapPin />}
            {locating ? t.location_loading : position ? t.location_refresh : t.location_use}
          </Button>
          {position && (
            <div className="mt-3 flex items-start gap-2 rounded-2xl bg-leaf-soft p-3 text-sm font-medium text-leaf-foreground">
              <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <p>{t.location_saved}</p>
            </div>
          )}
          {locationError && (
            <p role="alert" className="mt-3 rounded-2xl bg-warning-soft p-3 text-sm font-medium text-foreground">
              {locationError}
            </p>
          )}
          {position && (
            <Button
              type="button"
              variant="ghost"
              className="mt-2 w-full"
              onClick={() => {
                setPosition(null);
                setLocationError(null);
              }}
            >
              {t.location_remove}
            </Button>
          )}
        </section>

        <section className="rounded-2xl bg-muted p-4">
          <h2 className="text-sm font-bold">{t.privacy_title}</h2>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{t.privacy_text}</p>
        </section>

        <Button type="submit" variant="hero" size="xl" className="w-full">
          {profile ? t.save_edit : t.save}
        </Button>
      </form>
    </main>
  );
}
