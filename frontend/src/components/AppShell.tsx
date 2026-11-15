import { FlaskConical, Mic, Satellite, Users } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router';
import { toast, Toaster } from 'sonner';
import { usePlot } from '../context/PlotContext';
import { fr } from '../i18n/fr';
import { USE_MOCK } from '../services/api';
import { BottomNav } from './BottomNav';
import { Logo } from './Logo';
import { SplashScreen } from './SplashScreen';

const SCREENS = [
  { to: '/', label: fr.nav.home, desc: fr.nav.home_desc },
  { to: '/parcelle', label: fr.nav.farm, desc: fr.nav.farm_desc },
  { to: '/assistant', label: fr.nav.talk, desc: fr.nav.talk_desc },
  { to: '/prediction', label: fr.nav.climate, desc: fr.nav.climate_desc },
  { to: '/recommandation', label: fr.nav.crops, desc: fr.nav.crops_desc },
  { to: '/technique', label: fr.nav.technical, desc: fr.nav.technical_desc },
] as const;

const CHIP_ICONS = [Satellite, Users, Mic];

/** Les notifications restent 8 s : le temps de les lire sans se presser. */
const TOAST_MS = 8000;
/** Elles s'affichent en bas, au-dessus des onglets : elles ne couvrent jamais le titre de l'écran. */
const TOAST_BOTTOM_PX = 104;

function useOnline() {
  const [online, setOnline] = useState(() => navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, []);
  return online;
}

/**
 * Coque de l'application.
 * - Téléphone : plein écran ; bandeaux d'état fixes en haut, le contenu défile dessous, onglets collés en bas.
 * - Écran large : cadre de téléphone centré + panneau de présentation à gauche.
 * Les panneaux (PhoneSheet) et l'écran de démarrage se positionnent dans le cadre, ancêtre `relative`.
 */
export function AppShell() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const { pathname } = useLocation();
  const online = useOnline();
  const { plotsLoading } = usePlot();

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: 0 });
    // Une notification parle de l'écran où elle est née : elle ne suit pas l'utilisateur ailleurs.
    toast.dismiss();
  }, [pathname]);

  return (
    <div className="min-h-dvh lg:flex lg:items-center lg:justify-center lg:gap-16 lg:p-8">
      <aside className="hidden max-w-sm lg:block">
        <Logo />
        <p className="mt-8 text-xs font-bold tracking-[0.18em] text-primary uppercase">{fr.app.concept_eyebrow}</p>
        <p className="mt-3 font-display text-4xl leading-[1.05] font-bold tracking-tight text-foreground">
          {fr.app.concept_title}
        </p>
        <p className="mt-4 text-[15px] leading-relaxed text-muted-foreground">{fr.app.concept_text}</p>
        <ul className="mt-8 space-y-2">
          {SCREENS.map((s, i) => (
            <li key={s.to}>
              <NavLink
                to={s.to}
                end={s.to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-4 rounded-2xl border p-3 transition-colors ${
                    isActive ? 'border-border bg-card shadow-soft' : 'border-transparent hover:bg-card/70'
                  }`
                }
              >
                <span className="flex size-9 items-center justify-center rounded-xl bg-secondary font-display text-sm font-bold text-secondary-foreground">
                  {i + 1}
                </span>
                <span>
                  <span className="block font-semibold text-foreground">{s.label}</span>
                  <span className="block text-sm text-muted-foreground">{s.desc}</span>
                </span>
              </NavLink>
            </li>
          ))}
        </ul>
        <div className="mt-8 flex flex-wrap gap-2 text-xs font-medium text-muted-foreground">
          {fr.app.concept_chips.map((chip, i) => {
            const Icon = CHIP_ICONS[i] ?? Satellite;
            return (
              <span key={chip} className="inline-flex items-center gap-1.5 rounded-full bg-card/70 px-3 py-1.5">
                <Icon className="size-3.5" /> {chip}
              </span>
            );
          })}
        </div>
      </aside>

      <div className="relative mx-auto w-full overflow-hidden lg:mx-0 lg:w-[392px] lg:shrink-0 lg:rounded-[3rem] lg:bg-forest-deep lg:p-3 lg:shadow-lift">
        <div className="flex h-dvh flex-col overflow-hidden bg-background lg:h-[820px] lg:rounded-[2.4rem]">
          {/* Bandeaux d'état : hors de la zone défilante, donc toujours visibles. */}
          {!online && (
            <p role="status" className="shrink-0 bg-destructive px-4 py-1.5 text-center text-xs font-semibold text-destructive-foreground">
              {fr.app.offline_banner}
            </p>
          )}
          {USE_MOCK && (
            <p className="flex shrink-0 items-center justify-center gap-1.5 bg-sun px-4 py-1.5 text-center text-xs font-bold text-sun-foreground">
              <FlaskConical className="size-3.5 shrink-0" aria-hidden="true" />
              {fr.app.mock_banner}
            </p>
          )}
          <div
            ref={scrollRef}
            id="contenu"
            className="no-scrollbar flex min-h-0 flex-1 flex-col overflow-x-hidden overflow-y-auto"
          >
            <Outlet />
            <BottomNav />
          </div>
        </div>
        <SplashScreen ready={!plotsLoading} />
      </div>

      <Toaster
        position="bottom-center"
        duration={TOAST_MS}
        offset={{ bottom: TOAST_BOTTOM_PX }}
        mobileOffset={{ bottom: TOAST_BOTTOM_PX }}
        closeButton
        toastOptions={{
          classNames: {
            toast:
              '!rounded-2xl !border-border !bg-card !text-foreground !shadow-card !font-sans !text-[15px] !gap-3 !p-4',
            title: '!font-semibold',
            description: '!text-muted-foreground !text-sm',
            icon: '!text-primary',
          },
        }}
      />
    </div>
  );
}
