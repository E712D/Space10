import { CloudSun, Home, Map, MessagesSquare, Mic, Sprout, type LucideIcon } from 'lucide-react';
import { NavLink } from 'react-router';
import { fr } from '../i18n/fr';
import { cn } from '../lib/cn';

const ITEMS: Array<{ to: string; label: string; icon: LucideIcon; center?: true }> = [
  { to: '/', label: fr.nav.home, icon: Home },
  { to: '/parcelle', label: fr.nav.farm, icon: Map },
  { to: '/assistant', label: fr.nav.talk, icon: Mic, center: true },
  { to: '/prediction', label: fr.nav.climate, icon: CloudSun },
  { to: '/recommandation', label: fr.nav.crops, icon: Sprout },
];

const LABEL = 'text-xs font-semibold';

/**
 * Onglets bas : les cinq écrans du parcours agriculteur, l'onglet en cours est allumé.
 * Au centre, le gros bouton micro ouvre « Demander conseil ». Une fois sur cet écran, il devient
 * un onglet ordinaire : le seul micro visible est alors celui de l'écran, qui écoute vraiment.
 * L'Espace technique n'est pas ici : il reste hors du parcours agriculteur.
 */
export function BottomNav() {
  return (
    <nav
      aria-label={fr.nav.label}
      className="sticky bottom-0 z-40 mt-auto border-t border-border/70 bg-card/95 px-1 pt-1.5 pb-[max(env(safe-area-inset-bottom),0.5rem)] shadow-nav backdrop-blur-xl"
    >
      <ul className="grid grid-cols-5 items-start">
        {ITEMS.map((item) => {
          if (item.center) {
            return (
              <li key={item.to} className="flex min-w-0 justify-center">
                <NavLink to={item.to} className="group flex min-h-14 flex-col items-center justify-start gap-1">
                  {({ isActive }) =>
                    isActive ? (
                      <>
                        <span className="flex h-8 w-14 items-center justify-center rounded-full bg-leaf-soft text-primary">
                          <MessagesSquare className="size-[22px]" strokeWidth={2.4} aria-hidden="true" />
                        </span>
                        <span className={cn(LABEL, 'text-center leading-tight text-primary')}>{item.label}</span>
                      </>
                    ) : (
                      <>
                        <span className="relative -mt-7 flex size-16 items-center justify-center rounded-full bg-gradient-leaf text-leaf-foreground shadow-glow ring-4 ring-card transition-transform group-active:scale-95">
                          <span className="absolute inset-0 animate-pulse-ring rounded-full bg-leaf/50" />
                          <Mic className="relative size-7" strokeWidth={2.2} aria-hidden="true" />
                        </span>
                        <span className={cn(LABEL, 'text-center leading-tight text-muted-foreground')}>{item.label}</span>
                      </>
                    )
                  }
                </NavLink>
              </li>
            );
          }
          const Icon = item.icon;
          return (
            <li key={item.to} className="min-w-0">
              <NavLink
                to={item.to}
                end={item.to === '/'}
                className="flex min-h-14 flex-col items-center justify-start gap-1 rounded-2xl"
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={cn(
                        'flex h-8 w-14 items-center justify-center rounded-full transition-colors',
                        isActive ? 'bg-leaf-soft text-primary' : 'text-muted-foreground',
                      )}
                    >
                      <Icon className="size-[22px]" strokeWidth={isActive ? 2.4 : 2} aria-hidden="true" />
                    </span>
                    <span
                      className={cn(
                        LABEL,
                        'text-center leading-tight',
                        isActive ? 'font-bold text-primary' : 'text-muted-foreground',
                      )}
                    >
                      {item.label}
                    </span>
                  </>
                )}
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
