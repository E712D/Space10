import { AlertTriangle, RefreshCw } from 'lucide-react';
import type { ReactNode } from 'react';
import { fr } from '../i18n/fr';
import { cn } from '../lib/cn';
import type { ApiError } from '../services/errors';
import { Button } from './Button';

export type LoadingVariant = 'generic' | 'home' | 'weather' | 'farm' | 'climate' | 'crops' | 'technical';

function SkeletonBlock({ className }: { className: string }) {
  return <div className={cn('animate-pulse rounded-2xl bg-muted', className)} />;
}

function LoadingShape({ variant, lines }: { variant: LoadingVariant; lines: number }) {
  if (variant === 'weather') {
    return (
      <div className="rounded-3xl bg-sky-soft p-5">
        <SkeletonBlock className="h-4 w-2/5 bg-sky/30" />
        <SkeletonBlock className="mt-3 h-11 w-1/3 bg-sky/30" />
        <div className="mt-5 grid grid-cols-3 gap-2">
          {Array.from({ length: 3 }, (_, i) => <SkeletonBlock key={i} className="h-16 bg-sky/30" />)}
        </div>
        <div className="mt-4 flex justify-between gap-2">
          {Array.from({ length: 7 }, (_, i) => <SkeletonBlock key={i} className="h-12 flex-1 bg-sky/30" />)}
        </div>
      </div>
    );
  }

  if (variant === 'farm') {
    return (
      <div className="space-y-4">
        <div className="overflow-hidden rounded-3xl bg-card shadow-soft">
          <SkeletonBlock className="h-44 w-full rounded-none" />
          <div className="space-y-3 p-4">
            <SkeletonBlock className="h-6 w-2/3" />
            <SkeletonBlock className="h-4 w-1/2" />
            <div className="grid grid-cols-3 gap-2">
              {Array.from({ length: 3 }, (_, i) => <SkeletonBlock key={i} className="h-16" />)}
            </div>
          </div>
        </div>
        <SkeletonBlock className="h-20 w-full" />
        <SkeletonBlock className="h-14 w-full" />
      </div>
    );
  }

  if (variant === 'climate') {
    return (
      <div className="space-y-4">
        <div className="space-y-3 rounded-3xl bg-card p-4 shadow-soft">
          <SkeletonBlock className="h-4 w-1/3" />
          <SkeletonBlock className="h-8 w-2/3" />
          <SkeletonBlock className="h-2 w-full" />
        </div>
        <div className="space-y-4 rounded-3xl bg-card p-4 shadow-soft">
          <SkeletonBlock className="h-6 w-1/2" />
          <div className="flex gap-2">
            {Array.from({ length: 3 }, (_, i) => <SkeletonBlock key={i} className="h-10 flex-1" />)}
          </div>
          <SkeletonBlock className="h-48 w-full" />
        </div>
      </div>
    );
  }

  if (variant === 'crops') {
    return (
      <div className="space-y-4">
        <div className="overflow-hidden rounded-3xl bg-card shadow-soft">
          <SkeletonBlock className="h-44 w-full rounded-none" />
          <div className="space-y-3 p-4">
            <SkeletonBlock className="h-6 w-2/3" />
            <SkeletonBlock className="h-4 w-1/2" />
            <SkeletonBlock className="h-4 w-full" />
          </div>
        </div>
        {Array.from({ length: 2 }, (_, i) => (
          <SkeletonBlock key={i} className="h-20 w-full" />
        ))}
      </div>
    );
  }

  if (variant === 'technical') {
    return (
      <div className="space-y-3 rounded-3xl bg-card p-4 shadow-soft">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="flex items-center justify-between gap-4 py-1">
            <SkeletonBlock className="h-4 w-2/5" />
            <SkeletonBlock className="h-6 w-1/4" />
          </div>
        ))}
      </div>
    );
  }

  if (variant === 'home') {
    return (
      <div className="space-y-4">
        <div className="space-y-3 rounded-3xl bg-card p-5 shadow-soft">
          <SkeletonBlock className="h-4 w-2/5" />
          <SkeletonBlock className="h-10 w-1/3" />
          <SkeletonBlock className="h-24 w-full" />
        </div>
        <div className="overflow-hidden rounded-3xl bg-card shadow-soft">
          <SkeletonBlock className="h-36 w-full rounded-none" />
          <div className="space-y-3 p-4">
            <SkeletonBlock className="h-5 w-2/3" />
            <SkeletonBlock className="h-4 w-full" />
            <SkeletonBlock className="h-12 w-full" />
          </div>
        </div>
        <SkeletonBlock className="h-20 w-full" />
      </div>
    );
  }

  return (
    <>
      {Array.from({ length: lines }, (_, i) => (
        <div
          key={i}
          className="h-4 animate-pulse rounded-full bg-muted"
          style={{ width: `${90 - ((i * 17) % 45)}%` }}
        />
      ))}
    </>
  );
}

/** Squelette de chargement avec forme adaptée à l’écran ; `lines` reste disponible en mode générique. */
export function LoadingState({
  lines = 3,
  className,
  variant = 'generic',
}: {
  lines?: number;
  className?: string;
  variant?: LoadingVariant;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      className={cn(
        variant === 'generic' ? 'space-y-3 rounded-3xl bg-card p-4 shadow-soft' : 'space-y-4',
        className,
      )}
    >
      <span className="sr-only">{fr.common.loading}</span>
      <div aria-hidden="true">
        <LoadingShape variant={variant} lines={lines} />
      </div>
    </div>
  );
}

/** Erreur en français (message issu de ErrorEnvelope) avec « Réessayer » facultatif. */
export function ErrorState({ error, onRetry, className }: { error: ApiError; onRetry?: () => void; className?: string }) {
  return (
    <div role="alert" className={cn('rounded-3xl border border-destructive/25 bg-danger-soft p-4', className)}>
      <div className="flex items-start gap-3">
        <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-destructive text-destructive-foreground">
          <AlertTriangle className="size-5" />
        </span>
        <div className="min-w-0">
          <p className="font-bold text-foreground">{fr.common.error_title}</p>
          <p className="mt-0.5 text-sm break-words text-muted-foreground">{error.message}</p>
        </div>
      </div>
      {onRetry && (
        <Button variant="outline" className="mt-3 w-full" onClick={onRetry}>
          <RefreshCw /> {fr.common.retry}
        </Button>
      )}
    </div>
  );
}

/** État vide : titre, texte et actions facultatives. */
export function EmptyState({
  title,
  text,
  children,
  className,
}: {
  title: string;
  text?: string;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('rounded-3xl border-2 border-dashed border-border bg-card/60 p-6 text-center', className)}>
      <p className="font-display text-lg font-bold text-foreground">{title}</p>
      {text && <p className="mt-1 text-sm text-muted-foreground">{text}</p>}
      {children && <div className="mt-4 flex flex-col items-stretch gap-2">{children}</div>}
    </div>
  );
}
