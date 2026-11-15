import {
  AlertTriangle,
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  CloudRain,
  Droplets,
  Flame,
  Info,
  Loader2,
  Mountain,
  RefreshCw,
  ShieldCheck,
  SlidersHorizontal,
  Square,
  Thermometer,
  Volume2,
  type LucideIcon,
} from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import { AnalysisGate } from '../components/AnalysisGate';
import { BarChart, type BarPoint } from '../components/BarChart';
import { Button, ButtonLink } from '../components/Button';
import { Collapsible } from '../components/Collapsible';
import { ScreenHeader } from '../components/ScreenHeader';
import { ErrorState } from '../components/StateViews';
import { usePlot } from '../context/PlotContext';
import { useSpeechSynthesis } from '../hooks/useSpeechSynthesis';
import { formatDate, formatMonth, formatMonthYear, formatNumber, formatWithUnit } from '../i18n/format';
import { fr } from '../i18n/fr';
import { cn } from '../lib/cn';
import { nearestCity } from '../lib/visuals';
import type { AnalysisOut, BaselineComparison, CriticalPeriod, PredictedValue, PredictionOutput } from '../types/api';

const t = fr.climate;

type MetricKey = 'rain' | 'heat' | 'soil';
type CriticalKind = CriticalPeriod['kind'];

const METRIC_KEYS: MetricKey[] = ['rain', 'heat', 'soil'];

interface MetricStyle {
  icon: LucideIcon;
  tone: 'sky' | 'sun' | 'leaf';
  /** Pastille de l'icône dans le résumé. */
  soft: string;
  activeChip: string;
  /** Périodes à surveiller qui concernent cette mesure. */
  kinds: CriticalKind[];
  digits: number;
  baseline: number;
  /** Facteur d'affichage (l'humidité du sol est une fraction 0–1 dans l'API). */
  scale: number;
  pick: (period: PredictionOutput['periods'][number]) => PredictedValue;
}

const METRICS: Record<MetricKey, MetricStyle> = {
  rain: {
    icon: CloudRain,
    tone: 'sky',
    soft: 'bg-sky-soft text-sky-foreground',
    activeChip: 'bg-sky text-primary-foreground',
    kinds: ['heavy_rain', 'water_stress'],
    digits: 0,
    baseline: 0,
    scale: 1,
    pick: (p) => p.features.precip_mm,
  },
  heat: {
    icon: Thermometer,
    tone: 'sun',
    soft: 'bg-warning-soft text-sun-foreground',
    activeChip: 'bg-warning text-primary-foreground',
    kinds: ['heat_stress'],
    digits: 1,
    baseline: 20,
    scale: 1,
    pick: (p) => p.features.t2m_max_c,
  },
  soil: {
    icon: Droplets,
    tone: 'leaf',
    soft: 'bg-leaf-soft text-leaf-foreground',
    activeChip: 'bg-leaf text-leaf-foreground',
    kinds: ['water_stress', 'erosion'],
    digits: 0,
    baseline: 0,
    scale: 100,
    pick: (p) => p.features.sm_root,
  },
};

const KIND_STYLE: Record<CriticalKind, { icon: LucideIcon; bar: string }> = {
  heat_stress: { icon: Flame, bar: 'bg-earth text-primary-foreground' },
  heavy_rain: { icon: CloudRain, bar: 'bg-sky text-primary-foreground' },
  water_stress: { icon: AlertTriangle, bar: 'bg-warning text-primary-foreground' },
  erosion: { icon: Mountain, bar: 'bg-sun text-sun-foreground' },
};

const scaled = (value: number | null, scale: number): number | null => (value === null ? null : value * scale);

const mean = (values: Array<number | null>): number | null => {
  const known = values.filter((v): v is number => v !== null);
  return known.length === 0 ? null : known.reduce((sum, v) => sum + v, 0) / known.length;
};

interface MonthValue {
  period: string;
  value: number;
}

/** Mois où la valeur est la plus haute et la plus basse (mois sans donnée ignorés). */
const extremes = (points: MonthValue[]): { max: MonthValue; min: MonthValue } | null => {
  const first = points[0];
  if (!first) return null;
  let max = first;
  let min = first;
  for (const p of points) {
    if (p.value > max.value) max = p;
    if (p.value < min.value) min = p;
  }
  return { max, min };
};

/**
 * Phrase « en clair » d'une mesure, construite uniquement à partir des prévisions reçues
 * (mois le plus haut / le plus bas). Aucune valeur ni aucun conseil n'est ajouté.
 */
const insightFor = (metric: MetricKey, prediction: PredictionOutput): string => {
  const style = METRICS[metric];
  const unit = t.metrics[metric].unit;
  const known: MonthValue[] = prediction.periods.flatMap((p) => {
    const value = scaled(style.pick(p).value, style.scale);
    return value === null ? [] : [{ period: p.period, value }];
  });
  const ext = extremes(known);
  if (!ext) return t.no_data;
  const show = (m: MonthValue) => formatWithUnit(m.value, unit, style.digits);
  const single = ext.max.period === ext.min.period;
  const maxMonth = formatMonthYear(ext.max.period);
  const minMonth = formatMonthYear(ext.min.period);
  if (metric === 'rain') {
    return single ? t.rain_single(maxMonth, show(ext.max)) : t.rain_both(maxMonth, show(ext.max), minMonth, show(ext.min));
  }
  if (metric === 'heat') {
    const days = prediction.season_summary.heat_stress_days_total.value;
    const rounded = days === null ? null : Math.round(days);
    return `${t.heat_hottest(maxMonth, show(ext.max))} ${
      rounded === null ? t.heat_days_missing : t.heat_days(rounded, formatNumber(rounded))
    }`;
  }
  return single ? t.soil_single(maxMonth, show(ext.max)) : t.soil_both(minMonth, show(ext.min), maxMonth, show(ext.max));
};

/** 1. Résumé compréhensible, lisible à voix haute. */
function SummarySection({ prediction }: { prediction: PredictionOutput }) {
  const { supported, speaking, speak, cancel } = useSpeechSynthesis();
  const lines = METRIC_KEYS.map((key) => ({ key, label: t.metrics[key].label, text: insightFor(key, prediction) }));

  const listen = () => {
    if (!supported) {
      toast(fr.common.speech_unavailable);
      return;
    }
    if (speaking) cancel();
    else speak(lines.map((l) => `${l.label}. ${l.text}`).join(' '));
  };

  return (
    <section className="mx-5 animate-fade-up rounded-3xl bg-card p-4 shadow-card">
      <h2 className="text-lg font-bold">{t.summary_title}</h2>
      <ul className="mt-3 space-y-3">
        {lines.map(({ key, label, text }) => {
          const Icon = METRICS[key].icon;
          return (
            <li key={key} className="flex items-start gap-3">
              <span className={cn('flex size-10 shrink-0 items-center justify-center rounded-xl', METRICS[key].soft)}>
                <Icon className="size-5" aria-hidden="true" />
              </span>
              <p className="min-w-0 text-[15px] leading-snug">
                <span className="font-bold">{label} : </span>
                {text}
              </p>
            </li>
          );
        })}
      </ul>
      <Button variant="soft" size="lg" className="mt-4 w-full" onClick={listen}>
        {speaking ? <Square /> : <Volume2 />}
        {speaking ? t.summary_stop : t.summary_listen}
      </Button>
    </section>
  );
}

/** 2. Périodes à surveiller : le message est affiché directement, sans rien à déplier. */
function AlertsSection({ alerts }: { alerts: CriticalPeriod[] }) {
  return (
    <section className="mx-5 mt-6">
      <h2 className="mb-3 text-lg font-bold">{t.alerts}</h2>
      {alerts.length === 0 ? (
        <div className="flex items-center gap-3 rounded-3xl border border-leaf/30 bg-leaf-soft p-4">
          <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-leaf text-leaf-foreground">
            <CheckCircle2 className="size-5" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="font-bold">{t.no_alerts_title}</p>
            <p className="text-sm text-muted-foreground">{t.no_alerts_text}</p>
          </div>
        </div>
      ) : (
        <ul className="space-y-3">
          {alerts.map((a) => {
            const high = a.severity === 'high';
            const Icon = KIND_STYLE[a.kind].icon;
            return (
              <li
                key={`${a.period}-${a.kind}`}
                className={cn(
                  'rounded-3xl border p-4',
                  high ? 'border-warning/30 bg-warning-soft' : 'border-earth/20 bg-earth-soft',
                )}
              >
                <div className="flex items-center gap-3">
                  <span
                    className={cn(
                      'flex size-11 shrink-0 items-center justify-center rounded-2xl text-primary-foreground',
                      high ? 'bg-warning' : 'bg-earth',
                    )}
                  >
                    <Icon className="size-5" aria-hidden="true" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="font-bold">{fr.critical.kind[a.kind]}</p>
                    <p className="text-sm text-muted-foreground">
                      <span className="capitalize">{formatMonthYear(a.period)}</span> · {fr.critical.severity[a.severity]}
                    </p>
                  </div>
                </div>
                <p className="mt-3 rounded-2xl bg-card/80 p-3 text-[15px] leading-snug">{a.message_fr}</p>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/** 4. Calendrier : un mois par ligne, coloré quand il est à surveiller. */
function PeriodsSection({ prediction, season }: { prediction: PredictionOutput; season: AnalysisOut['season'] }) {
  return (
    <section className="mx-5 mt-6">
      <h2 className="mb-3 text-lg font-bold">{t.periods}</h2>
      <div className="rounded-3xl bg-card p-4 shadow-soft">
        {prediction.periods.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t.no_periods}</p>
        ) : (
          <ul className="space-y-2.5">
            {prediction.periods.map((p) => {
              const alerts = prediction.critical_periods.filter((c) => c.period === p.period);
              return (
                <li key={p.period} className="flex items-center gap-3">
                  <span className="w-10 shrink-0 text-sm font-bold text-muted-foreground capitalize">
                    {formatMonth(p.period)}
                  </span>
                  <div className="flex h-8 min-w-0 flex-1 gap-1 overflow-hidden rounded-full bg-muted">
                    {alerts.length === 0 ? (
                      <span className="flex flex-1 items-center px-3 text-xs font-semibold text-muted-foreground">
                        {t.calm_month}
                      </span>
                    ) : (
                      alerts.map((c) => (
                        <span
                          key={c.kind}
                          className={cn(
                            'flex min-w-0 flex-1 items-center justify-center rounded-full px-2 text-xs font-bold',
                            KIND_STYLE[c.kind].bar,
                          )}
                        >
                          <span className="truncate">{fr.critical.kind[c.kind]}</span>
                        </span>
                      ))
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        <div className="mt-4 flex items-start gap-2 rounded-2xl bg-leaf-soft p-3">
          <CalendarDays className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden="true" />
          <p className="min-w-0 text-sm font-semibold">
            <span className="font-bold">{fr.common.season(prediction.season_label)}</span>
            {' · '}
            {fr.common.from_to(formatDate(prediction.season_start), formatDate(prediction.season_end))}
            {' · '}
            {fr.common[season.status]}
          </p>
        </div>
      </div>
    </section>
  );
}

/** 5. Graphiques mois par mois, avec leur légende. */
function ChartsSection({ prediction }: { prediction: PredictionOutput }) {
  const [metric, setMetric] = useState<MetricKey>('rain');
  const { periods, season_summary: summary, critical_periods: critical } = prediction;

  const headline: Record<MetricKey, string> = {
    rain: formatNumber(summary.precip_total_mm.value),
    heat: formatNumber(mean(periods.map((p) => p.features.t2m_max_c.value)), 1),
    soil: formatNumber(scaled(mean(periods.map((p) => p.features.sm_root.value)), 100)),
  };

  const style = METRICS[metric];
  const text = t.metrics[metric];
  const available = periods.filter((p) => style.pick(p).value !== null).length;
  const availability =
    available === 0 ? t.data_missing : available < periods.length ? t.data_partial(available, periods.length) : null;

  const data: BarPoint[] = periods.map((p) => {
    const v = style.pick(p);
    return {
      label: formatMonth(p.period),
      value: scaled(v.value, style.scale),
      low: scaled(v.q10, style.scale),
      high: scaled(v.q90, style.scale),
      highlight: critical.some((c) => c.period === p.period && style.kinds.includes(c.kind)),
    };
  });
  const hasHighlight = data.some((d) => d.highlight);
  const hasRange = data.some((d) => d.low != null && d.high != null);
  const barSwatch = { sky: 'bg-sky', sun: 'bg-warning', leaf: 'bg-leaf' }[style.tone];

  return (
    <section className="mx-5 mt-6">
      <h2 className="mb-3 text-lg font-bold">{t.charts_title}</h2>
      <div className="grid grid-cols-3 gap-2" role="tablist" aria-label={t.metrics_label}>
        {METRIC_KEYS.map((key) => {
          const it = METRICS[key];
          const active = key === metric;
          const Icon = it.icon;
          return (
            <button
              key={key}
              type="button"
              role="tab"
              id={`climate-tab-${key}`}
              aria-selected={active}
              aria-controls="climate-panel"
              onClick={() => setMetric(key)}
              className={cn(
                'flex min-h-12 min-w-0 flex-col items-center gap-1 rounded-2xl border-2 px-1 py-3 transition active:scale-95',
                active ? cn(it.activeChip, 'border-transparent shadow-soft') : 'border-border bg-card text-foreground',
              )}
            >
              <Icon className="size-6" aria-hidden="true" />
              <span className="text-sm font-bold">{t.metrics[key].tab}</span>
              <span className="text-xs font-semibold opacity-90">
                {headline[key]}
                {headline[key] !== fr.common.not_available && ` ${t.metrics[key].unit}`}
              </span>
            </button>
          );
        })}
      </div>

      <article
        key={metric}
        id="climate-panel"
        role="tabpanel"
        aria-labelledby={`climate-tab-${metric}`}
        className="mt-3 animate-fade-up rounded-3xl bg-card p-4 shadow-card"
      >
        <h3 className="font-sans text-sm font-semibold tracking-normal text-muted-foreground">
          {t.chart_title(text.label, periods.length)}
        </h3>
        {availability && (
          <span className="mt-1 inline-flex rounded-full bg-warning-soft px-2.5 py-1 text-xs font-bold text-sun-foreground">
            {availability}
          </span>
        )}
        <div className="mt-3">
          <BarChart
            data={data}
            tone={style.tone}
            label={t.chart_alt(text.label)}
            digits={style.digits}
            baseline={style.baseline}
          />
        </div>
        <ul aria-label={t.legend_label} className="mt-2 space-y-1.5 text-sm text-muted-foreground">
          <li className="flex items-center gap-2">
            <span className={cn('h-3 w-5 shrink-0 rounded', barSwatch)} aria-hidden="true" />
            {t.legend_bar(text.unit)}
          </li>
          {hasHighlight && (
            <li className="flex items-center gap-2">
              <span className="h-3 w-5 shrink-0 rounded bg-destructive" aria-hidden="true" />
              {t.legend_highlight}
            </li>
          )}
          {hasRange && (
            <li className="flex items-center gap-2">
              <span className="flex h-3 w-5 shrink-0 justify-center" aria-hidden="true">
                <span className="h-full w-0.5 rounded bg-forest-deep" />
              </span>
              {t.legend_range}
            </li>
          )}
        </ul>
      </article>
    </section>
  );
}

const isReliable = (b: BaselineComparison): boolean => b.method === 'model' && b.skill_pct !== null && b.skill_pct >= 3;

/** 6. Informations techniques, repliées : fiabilité, sources, qualité des données. */
function TechnicalDetails({ prediction }: { prediction: PredictionOutput }) {
  const measures = prediction.baseline_comparison;
  const total = measures.length;
  const reliable = measures.filter(isReliable).length;
  const level =
    reliable === total
      ? t.reliability_levels.high
      : reliable >= total / 2
        ? t.reliability_levels.medium
        : t.reliability_levels.limited;

  const qualityOf = (key: MetricKey): string => {
    const qualities = new Set(
      prediction.periods.map((p) => METRICS[key].pick(p)).filter((v) => v.value !== null).map((v) => v.quality),
    );
    const [only] = [...qualities];
    return qualities.size === 0 || !only ? fr.quality.missing : qualities.size === 1 ? fr.quality[only] : t.quality_mixed;
  };

  return (
    <Collapsible title={t.technical_title} icon={SlidersHorizontal} className="mx-5 mt-6">
      <div className="texture-veins rounded-2xl bg-gradient-forest p-4 text-primary-foreground">
        <div className="flex items-center gap-3">
          <ShieldCheck className="size-7 shrink-0 text-leaf" aria-hidden="true" />
          <div className="min-w-0">
            <h3 className="font-sans text-sm font-medium tracking-normal opacity-80">{t.reliability}</h3>
            <p className="font-display text-xl leading-tight font-bold">
              {total === 0 ? fr.common.not_available : t.reliability_value(level, reliable, total)}
            </p>
          </div>
        </div>
        {total > 0 && (
          <div className="mt-3 flex gap-1" aria-hidden="true">
            {measures.map((b) => (
              <span
                key={b.target}
                className={cn('h-2 flex-1 rounded-full', isReliable(b) ? 'bg-leaf' : 'bg-primary-foreground/20')}
              />
            ))}
          </div>
        )}
      </div>

      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
        {t.sources_text(prediction.model_version, formatDate(prediction.forecast_origin))}
      </p>

      {total > 0 && (
        <>
          <h3 className="mt-4 font-sans text-sm font-bold tracking-normal">{t.sources_list}</h3>
          <ul className="mt-1.5 space-y-1.5">
            {measures.map((b) => (
              <li key={b.target} className="flex items-start gap-2 text-sm leading-snug">
                <span
                  className={cn('mt-1.5 size-2 shrink-0 rounded-full', isReliable(b) ? 'bg-leaf' : 'bg-muted-foreground/40')}
                  aria-hidden="true"
                />
                <span>
                  <span className="font-bold">{fr.targets[b.target] ?? b.target}</span>
                  {' · '}
                  {b.method === 'model' && b.skill_pct !== null
                    ? t.source_gain(formatNumber(b.skill_pct, 1), b.skill_pct > 0)
                    : t.source_climatology}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}

      <h3 className="mt-4 font-sans text-sm font-bold tracking-normal">{t.quality_title}</h3>
      <ul className="mt-1.5 space-y-1.5 text-sm">
        {METRIC_KEYS.map((key) => (
          <li key={key} className="flex items-center justify-between gap-3">
            <span className="font-semibold">{t.metrics[key].label}</span>
            <span className="text-muted-foreground">{qualityOf(key)}</span>
          </li>
        ))}
      </ul>
    </Collapsible>
  );
}

function ClimateContent({ analysis }: { analysis: AnalysisOut }) {
  const { analysisRunning, analysisError, runAnalysis } = usePlot();
  const { prediction, season } = analysis;

  return (
    <>
      <SummarySection prediction={prediction} />
      <AlertsSection alerts={prediction.critical_periods} />

      {prediction.warnings.length > 0 && (
        <section className="mx-5 mt-6">
          <h2 className="mb-3 text-lg font-bold">{t.notes}</h2>
          <ul className="space-y-2.5 rounded-3xl bg-card p-4 shadow-soft">
            {prediction.warnings.map((w) => (
              <li key={w} className="flex items-start gap-2.5 text-[15px] leading-snug">
                <Info className="mt-0.5 size-5 shrink-0 text-sky" aria-hidden="true" />
                <span>{w}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <PeriodsSection prediction={prediction} season={season} />
      <ChartsSection prediction={prediction} />
      <TechnicalDetails prediction={prediction} />

      <div className="mx-5 mt-6 space-y-3">
        <ButtonLink to="/recommandation" variant="hero" size="xl" className="w-full">
          {t.next} <ArrowRight />
        </ButtonLink>
        {season.status === 'draft' && (
          <>
            <Button variant="outline" className="w-full" disabled={analysisRunning} onClick={() => void runAnalysis()}>
              {analysisRunning ? <Loader2 className="animate-spin" /> : <RefreshCw />}
              {analysisRunning ? fr.analyze.running : fr.analyze.again}
            </Button>
            {analysisError && !analysisRunning && <ErrorState error={analysisError} onRetry={() => void runAnalysis()} />}
          </>
        )}
      </div>
    </>
  );
}

export function PredictionPage() {
  const { activePlot } = usePlot();
  const city = activePlot ? nearestCity(activePlot.latitude, activePlot.longitude) : null;
  const eyebrow = activePlot ? (city ? `${activePlot.name} · ${city}` : activePlot.name) : undefined;

  return (
    <main className="flex-1 pb-6">
      <ScreenHeader eyebrow={eyebrow} title={fr.nav.climate} />
      <AnalysisGate>{(analysis) => <ClimateContent analysis={analysis} />}</AnalysisGate>
    </main>
  );
}
