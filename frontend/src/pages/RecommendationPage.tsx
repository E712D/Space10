import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  FileText,
  Info,
  Leaf,
  ListOrdered,
  Loader2,
  Lock,
  RefreshCw,
  Square,
  Star,
  Volume2,
} from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import { AnalysisGate } from '../components/AnalysisGate';
import { Button } from '../components/Button';
import { Collapsible } from '../components/Collapsible';
import { DesiredCropSection } from '../components/DesiredCropSection';
import { PhoneSheet } from '../components/PhoneSheet';
import { ScoreRing } from '../components/ScoreRing';
import { ScreenHeader } from '../components/ScreenHeader';
import { ErrorState } from '../components/StateViews';
import { CropThumb, hasCropImage, IllustrationTag } from '../components/Thumbs';
import { usePlot } from '../context/PlotContext';
import { useAsync } from '../hooks/useAsync';
import { useSpeechSynthesis } from '../hooks/useSpeechSynthesis';
import { formatDate } from '../i18n/format';
import { fr } from '../i18n/fr';
import { cn } from '../lib/cn';
import { suitability, type Tone } from '../lib/visuals';
import { api } from '../services/api';
import { toApiError, type ApiError } from '../services/errors';
import type { AnalysisOut, CropScore, PlotOut } from '../types/api';

const t = fr.crops;

const TONE_CHIP: Record<Tone, string> = {
  leaf: 'bg-leaf-soft text-leaf-foreground',
  sky: 'bg-sky-soft text-sky-foreground',
  sun: 'bg-warning-soft text-sun-foreground',
  earth: 'bg-earth-soft text-foreground',
};

const capitalize = (code: string) => code.charAt(0).toUpperCase() + code.slice(1).replace(/_/g, ' ');

function Bullets({ items, tone }: { items: readonly string[]; tone: 'leaf' | 'warning' }) {
  return (
    <ul className="space-y-2">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2.5 text-[15px] leading-snug">
          <span
            className={cn('mt-[7px] size-2 shrink-0 rounded-full', tone === 'leaf' ? 'bg-leaf' : 'bg-warning')}
            aria-hidden="true"
          />
          <span className="min-w-0 break-words">{item}</span>
        </li>
      ))}
    </ul>
  );
}

/**
 * 1. La culture conseillée, son explication et « Écouter » : tout ce qu'il faut pour décider,
 * visible sans défiler. « Écouter » lit le bilan de la saison fourni par le serveur.
 */
function MainCropCard({ crop, reportText }: { crop: CropScore; reportText: string }) {
  const level = suitability(crop.score);
  const synthesis = useSpeechSynthesis();

  const listen = () => {
    if (!synthesis.supported) {
      toast(fr.common.speech_unavailable);
      return;
    }
    if (synthesis.speaking) synthesis.cancel();
    else synthesis.speak(reportText);
  };

  return (
    <section className="mx-5 animate-fade-up" aria-labelledby="crops-main-title">
      <article className="overflow-hidden rounded-3xl bg-card shadow-card">
        <div className="relative h-36">
          <CropThumb cropCode={crop.crop_code} alt={t.illustration_alt(crop.name_fr)} className="absolute inset-0 size-full" />
          <div className="absolute inset-0 bg-gradient-fade" />
          <span
            className={cn(
              'absolute top-3 left-3 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold',
              TONE_CHIP[level.tone],
            )}
          >
            {level.label}
          </span>
          {hasCropImage(crop.crop_code) && <IllustrationTag className="top-3 right-3" />}
          <div className="absolute right-4 bottom-3 rounded-full bg-card p-1 shadow-soft">
            <ScoreRing value={crop.score} tone={level.tone} size={64} />
          </div>
          <div className="absolute right-24 bottom-3 left-4 text-primary-foreground">
            <h2 id="crops-main-title" className="font-sans text-sm font-semibold tracking-normal opacity-90">
              {t.main_title}
            </h2>
            <p className="font-display text-3xl leading-tight font-bold break-words">{crop.name_fr}</p>
          </div>
        </div>
        <div className="space-y-4 p-4">
          {crop.reasons.length > 0 && (
            <div>
              <h3 className="mb-2 font-bold">{t.why}</h3>
              <Bullets items={crop.reasons} tone="leaf" />
            </div>
          )}
          {crop.penalties.length > 0 && (
            <div className="rounded-2xl bg-warning-soft p-3">
              <h3 className="mb-2 font-bold">{t.weak_points}</h3>
              <Bullets items={crop.penalties} tone="warning" />
            </div>
          )}
          <Button variant="leaf" size="lg" className="w-full" onClick={listen}>
            {synthesis.speaking ? <Square /> : <Volume2 />}
            {synthesis.speaking ? t.stop : t.listen}
          </Button>
        </div>
      </article>
    </section>
  );
}

/** Ligne compacte d'une culture : image, nom, première raison, note. */
function CropRow({ crop, label, rank, star }: { crop: CropScore; label?: string; rank?: number; star?: boolean }) {
  const level = suitability(crop.score);
  const reason = crop.reasons[0];
  return (
    <div className="flex items-center gap-3 rounded-2xl bg-muted p-3">
      {rank !== undefined && (
        <span
          className="flex size-8 shrink-0 items-center justify-center rounded-full bg-secondary font-display text-sm font-bold text-secondary-foreground"
          aria-label={t.rank(rank)}
        >
          {rank}
        </span>
      )}
      <CropThumb cropCode={crop.crop_code} alt="" className="size-16 shrink-0 rounded-2xl" />
      <div className="min-w-0 flex-1">
        {label && <p className="text-xs font-semibold text-muted-foreground">{label}</p>}
        <p className="flex items-center gap-1.5 font-bold">
          <span className="truncate">{crop.name_fr}</span>
          {star && <Star className="size-4 shrink-0 fill-sun text-sun" role="img" aria-label={t.main_star} />}
        </p>
        <span className={cn('mt-0.5 inline-flex rounded-full px-2.5 py-0.5 text-xs font-bold', TONE_CHIP[level.tone])}>
          {level.label}
        </span>
        {reason && <p className="mt-1 text-sm leading-snug text-muted-foreground">{reason}</p>}
      </div>
      <ScoreRing value={crop.score} tone={level.tone} size={48} />
    </div>
  );
}

function CoverCrops({ codes }: { codes: string[] }) {
  // Noms français résolus via la liste des cultures ; repli sur le code tant qu'elle n'est pas disponible.
  const { data } = useAsync(() => api.getCrops(), []);
  const nameOf = (code: string) => data?.find((c) => c.code === code)?.name_fr ?? capitalize(code);
  return (
    <>
      <p className="mb-3 text-sm text-muted-foreground">{t.cover_hint}</p>
      <ul className="flex flex-wrap gap-2">
        {codes.map((code) => (
          <li
            key={code}
            className="inline-flex items-center gap-1.5 rounded-full bg-leaf-soft px-3.5 py-2 text-sm font-bold text-leaf-foreground"
          >
            <Leaf className="size-4" aria-hidden="true" /> {nameOf(code)}
          </li>
        ))}
      </ul>
    </>
  );
}

function DecisionSection({ analysis, plot }: { analysis: AnalysisOut; plot: PlotOut }) {
  const { applyLockedReport } = usePlot();
  const [open, setOpen] = useState(false);
  const [locking, setLocking] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const { season, report, recommendation } = analysis;

  if (season.status !== 'draft') {
    const isLocked = season.status === 'locked';
    return (
      <section className="mx-5 mt-6">
        <div className="texture-veins rounded-3xl bg-gradient-forest p-4 text-primary-foreground shadow-card">
          <div className="flex items-center gap-3">
            <div className="flex size-14 shrink-0 items-center justify-center rounded-2xl bg-primary-foreground/15">
              {isLocked ? <Lock className="size-7 text-leaf" /> : <CheckCircle2 className="size-7 text-leaf" />}
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="font-display text-2xl font-bold">{isLocked ? t.locked_title : t.closed_title}</h2>
              <p className="text-sm font-medium opacity-90">
                {isLocked
                  ? `${report.locked_at ? `${t.locked_on(formatDate(report.locked_at))} ` : ''}${t.locked_text}`
                  : t.closed_text}
              </p>
            </div>
          </div>
        </div>
      </section>
    );
  }

  const close = () => {
    if (locking) return;
    setOpen(false);
    setError(null);
  };

  const lock = async () => {
    setLocking(true);
    setError(null);
    try {
      const locked = await api.lockSeason(plot.plot_id, season.season_label);
      applyLockedReport(locked);
      setOpen(false);
      toast.success(t.lock_success, { description: t.lock_success_text });
    } catch (e) {
      setError(toApiError(e));
    } finally {
      setLocking(false);
    }
  };

  return (
    <section className="mx-5 mt-6">
      <h2 className="mb-3 text-lg font-bold">{t.decision_title}</h2>
      <div className="rounded-3xl bg-card p-4 shadow-soft">
        <p className="text-[15px] leading-snug">{t.decision_text}</p>
        <p className="mt-2 text-sm font-semibold text-muted-foreground">{t.auto_lock(formatDate(season.lock_date))}</p>
        {/* Action irréversible : volontairement moins voyante que l'action principale de l'écran. */}
        <Button variant="soft" size="lg" className="mt-4 w-full" onClick={() => setOpen(true)}>
          <Lock /> {t.lock_button}
        </Button>
      </div>

      <PhoneSheet open={open} onClose={close} title={t.confirm_title}>
        <div className="space-y-4 overflow-y-auto px-5 pt-1 pb-[max(env(safe-area-inset-bottom),1.25rem)]">
          <p className="text-[15px] leading-relaxed">
            {t.confirm_text(recommendation.main_crop.name_fr, season.season_label)}
          </p>
          {error && <ErrorState error={error} />}
          <div className="flex flex-col-reverse gap-3">
            <Button variant="outline" size="lg" disabled={locking} onClick={close}>
              {fr.common.cancel}
            </Button>
            <Button variant="hero" size="lg" disabled={locking} onClick={() => void lock()}>
              {locking ? <Loader2 className="animate-spin" /> : <Lock />}
              {locking ? t.locking : t.confirm_yes}
            </Button>
          </div>
        </div>
      </PhoneSheet>
    </section>
  );
}

function RerunSection() {
  const { analysisRunning, analysisError, runAnalysis } = usePlot();
  return (
    <div className="mx-5 mt-4 space-y-3">
      <Button variant="outline" size="lg" className="w-full" disabled={analysisRunning} onClick={() => void runAnalysis()}>
        {analysisRunning ? <Loader2 className="animate-spin" /> : <RefreshCw />}
        {analysisRunning ? fr.analyze.running : fr.analyze.again}
      </Button>
      {analysisRunning && (
        <p role="status" className="text-center text-sm text-muted-foreground">
          {fr.analyze.running_hint}
        </p>
      )}
      {analysisError && !analysisRunning && <ErrorState error={analysisError} onRetry={() => void runAnalysis()} />}
    </div>
  );
}

function CropsContent({ analysis, plot }: { analysis: AnalysisOut; plot: PlotOut }) {
  const { recommendation, report, season } = analysis;
  const mainCode = recommendation.main_crop.crop_code;
  const listed = [recommendation.next_crop, ...recommendation.top_3].filter((c): c is CropScore => c !== null);
  const showsImages = listed.some((c) => hasCropImage(c.crop_code));

  return (
    <>
      {/* 1. L'essentiel : culture, pourquoi, écouter. */}
      <MainCropCard crop={recommendation.main_crop} reportText={report.text_fr} />

      {/* 2. Ce qu'il faut surveiller. */}
      {recommendation.warnings.length > 0 && (
        <section className="mx-5 mt-6">
          <h2 className="mb-3 text-lg font-bold">{t.warnings_title}</h2>
          <div className="flex gap-3 rounded-3xl border border-warning/30 bg-warning-soft p-4">
            <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-warning text-primary-foreground">
              <AlertTriangle className="size-5" aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1 pt-0.5">
              <Bullets items={recommendation.warnings} tone="warning" />
            </div>
          </div>
        </section>
      )}

      {/* 3. Informations secondaires, repliées. */}
      <div className="mx-5 mt-6 space-y-3">
        {recommendation.next_crop && (
          <Collapsible title={t.next_title} icon={CalendarClock}>
            <CropRow crop={recommendation.next_crop} label={t.next_label} />
          </Collapsible>
        )}
        {recommendation.top_3.length > 0 && (
          <Collapsible title={t.top_title} icon={ListOrdered}>
            <ol className="space-y-2">
              {recommendation.top_3.map((crop, i) => (
                <li key={crop.crop_code}>
                  <CropRow crop={crop} rank={i + 1} star={crop.crop_code === mainCode} />
                </li>
              ))}
            </ol>
          </Collapsible>
        )}
        {recommendation.cover_crops.length > 0 && (
          <Collapsible title={t.cover_title} icon={Leaf}>
            <CoverCrops codes={recommendation.cover_crops} />
          </Collapsible>
        )}
        {recommendation.missing_info.length > 0 && (
          <Collapsible title={t.missing_title} icon={Info}>
            <ul className="space-y-2">
              {recommendation.missing_info.map((item, i) => (
                <li key={i} className="text-[15px] leading-snug break-words">
                  {item}
                </li>
              ))}
            </ul>
          </Collapsible>
        )}
        <Collapsible title={t.report_title} icon={FileText}>
          <span className="inline-flex rounded-full bg-secondary px-2.5 py-1 text-xs font-bold text-secondary-foreground">
            {t.report_version(report.version)}
          </span>
          <p className="mt-3 text-[15px] leading-relaxed break-words whitespace-pre-line">{report.text_fr}</p>
        </Collapsible>
        {showsImages && <p className="text-xs font-medium text-muted-foreground">{t.illustrations_note}</p>}
      </div>

      {/* 4. Décision. */}
      <DecisionSection analysis={analysis} plot={plot} />
      {season.status === 'draft' && <RerunSection />}
    </>
  );
}

export function RecommendationPage() {
  const { activePlot, analysis } = usePlot();
  const eyebrow = activePlot
    ? analysis
      ? `${activePlot.name} · ${fr.common.season(analysis.season.season_label)}`
      : activePlot.name
    : undefined;
  return (
    <main className="flex-1 pb-6">
      <ScreenHeader eyebrow={eyebrow} title={fr.nav.crops} />
      {activePlot && <DesiredCropSection analysis={analysis} />}
      <AnalysisGate loadingVariant="crops">{(a, plot) => <CropsContent analysis={a} plot={plot} />}</AnalysisGate>
    </main>
  );
}
