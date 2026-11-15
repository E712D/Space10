import { ChevronDown, type LucideIcon } from 'lucide-react';
import { useId, useState, type ReactNode } from 'react';
import { cn } from '../lib/cn';

interface CollapsibleProps {
  title: string;
  icon?: LucideIcon;
  children: ReactNode;
  defaultOpen?: boolean;
  className?: string;
}

/**
 * Section secondaire repliée par défaut : un grand bouton-titre, le contenu s'ouvre dessous.
 * Sert à garder l'essentiel en haut de l'écran sans retirer d'information.
 */
export function Collapsible({ title, icon: Icon, children, defaultOpen = false, className }: CollapsibleProps) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <section className={cn('overflow-hidden rounded-3xl bg-card shadow-soft', className)}>
      <h2 className="font-sans tracking-normal">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={id}
          onClick={() => setOpen((v) => !v)}
          className="flex min-h-14 w-full items-center gap-3 px-4 py-3 text-left text-base font-bold transition active:bg-muted"
        >
          {Icon && (
            <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-secondary text-secondary-foreground">
              <Icon className="size-5" aria-hidden="true" />
            </span>
          )}
          <span className="min-w-0 flex-1">{title}</span>
          <ChevronDown
            className={cn('size-5 shrink-0 text-muted-foreground transition-transform', open && 'rotate-180')}
            aria-hidden="true"
          />
        </button>
      </h2>
      {open && (
        <div id={id} className="animate-fade-in px-4 pb-4">
          {children}
        </div>
      )}
    </section>
  );
}
