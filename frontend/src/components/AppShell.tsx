import { FlaskConical } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Outlet, useLocation } from 'react-router';
import { toast, Toaster } from 'sonner';
import { usePlot } from '../context/PlotContext';
import { fr } from '../i18n/fr';
import { USE_MOCK } from '../services/api';
import { BottomNav } from './BottomNav';
import { SplashScreen } from './SplashScreen';

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
 * L'application utilise une vraie largeur mobile, sans panneau de présentation ni coque
 * décorative : sur téléphone elle occupe tout l'écran, et sur écran large elle reste lisible
 * dans une largeur de travail mobile.
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
    <div className="min-h-dvh bg-background">
      <div className="relative mx-auto w-full max-w-md overflow-hidden">
        <div className="flex h-dvh flex-col overflow-hidden bg-background">
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
