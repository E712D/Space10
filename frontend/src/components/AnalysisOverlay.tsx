import { CloudSun, Satellite, Sprout } from 'lucide-react';
import { useEffect, useRef } from 'react';
import { formatCoords } from '../i18n/format';
import { fr } from '../i18n/fr';
import { nearestCity } from '../lib/visuals';
import type { PlotOut } from '../types/api';
import { Button } from './Button';

const STEP_ICONS = [Satellite, CloudSun, Sprout];

interface AnalysisOverlayProps {
  plot: PlotOut;
  /** Masque le panneau sans annuler la préparation des conseils. */
  onHide: () => void;
}

/**
 * Panneau affiché pendant la préparation des conseils (dans le cadre du téléphone).
 * Le serveur ne renvoie aucune progression : on n'affiche donc ni étapes cochées ni pourcentage,
 * seulement ce qui est en train d'être fait et une barre d'attente indéterminée.
 * C'est le parent qui démonte le panneau à la fin de l'appel.
 */
export function AnalysisOverlay({ plot, onHide }: AnalysisOverlayProps) {
  const sheetRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    sheetRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onHide();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onHide]);

  const place = nearestCity(plot.latitude, plot.longitude) ?? formatCoords(plot.latitude, plot.longitude);

  return (
    <div
      className="absolute inset-0 z-50 flex animate-fade-in items-end bg-overlay backdrop-blur-sm lg:inset-3 lg:overflow-hidden lg:rounded-[2.4rem]"
      role="dialog"
      aria-modal="true"
      aria-label={fr.analyze.running}
    >
      <div
        ref={sheetRef}
        tabIndex={-1}
        className="no-scrollbar max-h-full w-full animate-sheet-up overflow-y-auto rounded-t-[2rem] bg-card p-6 pb-8 outline-none"
      >
        <div className="relative mx-auto flex size-24 items-center justify-center" aria-hidden="true">
          <span className="absolute inset-0 animate-pulse-ring rounded-full bg-leaf/50" />
          <span className="relative flex size-20 items-center justify-center rounded-full bg-gradient-leaf text-leaf-foreground shadow-glow">
            <Sprout className="size-10" />
          </span>
        </div>
        <h2 className="mt-4 text-center font-display text-2xl font-bold">{fr.analyze.running}</h2>
        <p className="text-center text-sm text-muted-foreground">
          {plot.name} · {place}
        </p>

        <div
          className="mt-4 h-2 overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-label={fr.analyze.running}
          aria-busy="true"
        >
          <div className="h-full w-1/3 animate-indeterminate rounded-full bg-leaf" />
        </div>
        <p className="mt-2 text-center text-sm text-muted-foreground" role="status">
          {fr.analyze.running_hint}
        </p>

        <p className="mt-5 text-sm font-bold text-muted-foreground">{fr.analyze.steps_title}</p>
        <ul className="mt-2 space-y-2">
          {fr.analyze.steps.map((label, i) => {
            const Icon = STEP_ICONS[i] ?? Sprout;
            return (
              <li key={label} className="flex items-center gap-3 rounded-2xl bg-muted p-3">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-card text-primary">
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                <span className="text-[15px] font-semibold">{label}</span>
              </li>
            );
          })}
        </ul>

        <Button variant="soft" size="lg" className="mt-4 w-full" onClick={onHide}>
          {fr.analyze.hide}
        </Button>
      </div>
    </div>
  );
}
