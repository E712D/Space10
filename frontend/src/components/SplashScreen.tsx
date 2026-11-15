import { useEffect, useState } from 'react';
import { fr } from '../i18n/fr';
import { cn } from '../lib/cn';
import { LogoMark } from './Logo';

/** Durée minimale d'affichage, pour que l'écran ne clignote pas. */
const MIN_MS = 1400;
/** Durée maximale : au-delà, on laisse la main même si le chargement n'est pas fini. */
const MAX_MS = 4000;
const FADE_MS = 400;

const DOT_DELAYS = ['0ms', '160ms', '320ms'];

/**
 * Écran de démarrage, affiché dans le cadre du téléphone à l'ouverture de l'application.
 * Il reste au moins MIN_MS, puis disparaît dès que `ready` est vrai (ou après MAX_MS).
 * Un appui le ferme tout de suite. Même apparence que le repli statique de index.html.
 */
export function SplashScreen({ ready }: { ready: boolean }) {
  const [minElapsed, setMinElapsed] = useState(false);
  const [maxElapsed, setMaxElapsed] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [gone, setGone] = useState(false);

  useEffect(() => {
    const min = window.setTimeout(() => setMinElapsed(true), MIN_MS);
    const max = window.setTimeout(() => setMaxElapsed(true), MAX_MS);
    return () => {
      window.clearTimeout(min);
      window.clearTimeout(max);
    };
  }, []);

  const leaving = dismissed || maxElapsed || (minElapsed && ready);

  useEffect(() => {
    if (!leaving) return;
    const timer = window.setTimeout(() => setGone(true), FADE_MS);
    return () => window.clearTimeout(timer);
  }, [leaving]);

  if (gone) return null;

  return (
    <div
      role="status"
      aria-label={fr.app.splash_label}
      onClick={() => setDismissed(true)}
      className={cn(
        'texture-veins absolute inset-0 z-[70] flex flex-col items-center justify-center gap-5 bg-gradient-forest px-8 text-center text-primary-foreground transition-opacity duration-[400ms] lg:inset-3 lg:rounded-[2.4rem]',
        leaving && 'pointer-events-none opacity-0',
      )}
    >
      <LogoMark className="size-24 animate-float-soft rounded-[2rem] bg-primary-foreground/15 shadow-lift [&_svg]:size-14" />
      <div>
        <p className="font-display text-5xl leading-none font-bold tracking-tight">{fr.app.name}</p>
        <p className="mt-2 text-base font-semibold opacity-90">{fr.app.subtitle}</p>
      </div>
      <p className="max-w-[16rem] text-[15px] leading-snug opacity-90">{fr.app.splash_tagline}</p>
      <div className="mt-2 flex items-center gap-2" aria-hidden="true">
        {DOT_DELAYS.map((delay) => (
          <span key={delay} className="size-2.5 animate-dot rounded-full bg-leaf" style={{ animationDelay: delay }} />
        ))}
      </div>
    </div>
  );
}
