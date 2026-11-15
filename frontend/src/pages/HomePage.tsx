import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  CloudRain,
  CloudSun,
  Droplets,
  Info,
  Loader2,
  Lock,
  Map,
  MapPin,
  RefreshCw,
  ScanLine,
  Sprout,
  Sun,
  TrendingUp,
  type LucideIcon,
} from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { Link } from 'react-router';
import { AddPlotSheet } from '../components/AddPlotSheet';
import { AnalysisOverlay } from '../components/AnalysisOverlay';
import { Button, ButtonLink, buttonClasses } from '../components/Button';
import { ScoreRing } from '../components/ScoreRing';
import { EmptyState, ErrorState, LoadingState } from '../components/StateViews';
import { CropThumb, hasCropImage, hasPlotImage, IllustrationTag, PlotThumb } from '../components/Thumbs';
import { usePlot } from '../context/PlotContext';
import { useProfile } from '../context/ProfileContext';
import { useAdvice } from '../hooks/useAdvice';
import { useAsync } from '../hooks/useAsync';
import { useCurrentSeason } from '../hooks/useCurrentSeason';
import {
  formatLongDay,
  formatMonthYear,
  formatNumber,
  formatShortDay,
  formatWeekday,
  formatWithUnit,
  initials,
} from '../i18n/format';
import { fr } from '../i18n/fr';
import { cn } from '../lib/cn';
import { lastCropCode, nearestCity, plotStatus, STATUS_CHIP, suitability } from '../lib/visuals';
import { api } from '../services/api';
import type { CurrentSeasonOut, PlotOut } from '../types/api';

const t = fr.home;

const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/** En dessous de cet écart (fraction d'humidité du sol), la tendance est dite « stable ». */
const TREND_EPSILON = 0.005;

const trendLabel = (change: number | null): string =>
  change === null
    ? fr.common.not_available
    : change > TREND_EPSILON
      ? t.trend_up
      : change < -TREND_EPSILON
        ? t.trend_down
        : t.trend_stable;

const degrees = (value: number | null | undefined): string =>
  value === null || value === undefined ? fr.common.not_available : t.degrees(formatNumber(value));

/** Contenu commun du gros bouton d'action : pastille icône, titre, sous-titre, flèche. */
function HeroContent({ icon: Icon, spin, title, subtitle }: { icon: LucideIcon; spin?: boolean; title: string; subtitle: string }) {
  return (
    <>
      <span className="flex min-w-0 items-center gap-3">
        <span className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-primary-foreground/15">
          <Icon className={cn('!size-7', spin && 'animate-spin')} aria-hidden="true" />
        </span>
        <span className="min-w-0 text-left whitespace-normal">
          <span className="block text-lg leading-tight font-bold">{title}</span>
          <span className="block text-[13px] leading-snug font-medium opacity-80">{subtitle}</span>
        </span>
      </span>
      <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-leaf text-leaf-foreground">
        <ChevronRight className="!size-6" aria-hidden="true" />
      </span>
    </>
  );
}

const HERO = 'relative h-auto min-h-20 w-full justify-between overflow-hidden py-3 pr-3 pl-5 texture-veins';

/** Relevés météo des jours passés pour le champ actif (ce ne sont pas des prévisions). */
function WeatherCard({ plot, current }: { plot: PlotOut; current: CurrentSeasonOut }) {
  const last = current.series_30d[current.series_30d.length - 1];
  const week = current.series_30d.slice(-7);
  const BigIcon = current.precip_7d_mm !== null && current.precip_7d_mm > 20 ? CloudRain : CloudSun;
  const soilPct = last?.sm_root === null || last?.sm_root === undefined ? null : last.sm_root * 100;
  const city = nearestCity(plot.latitude, plot.longitude);
  const tiles = [
    { icon: CloudRain, value: formatWithUnit(current.precip_7d_mm, fr.units.mm), label: t.rain_7d },
    { icon: Droplets, value: formatWithUnit(soilPct, fr.units.pct), label: t.soil_moisture },
    { icon: TrendingUp, value: trendLabel(current.trend.sm_root_7d_change), label: t.soil_trend },
  ];

  return (
    <section className="mx-5 mt-5 animate-fade-up overflow-hidden rounded-3xl bg-gradient-sky p-5 text-primary-foreground shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-sans text-sm font-bold tracking-normal opacity-90">{t.weather_title}</h2>
          {city && (
            <p className="mt-0.5 flex items-center gap-1.5 text-sm font-semibold opacity-90">
              <MapPin className="size-4 shrink-0" aria-hidden="true" />
              <span className="truncate">{city}</span>
            </p>
          )}
          <p
            className={cn(
              'mt-1 font-display leading-none font-bold',
              last?.t2m_max_c === null || last?.t2m_max_c === undefined ? 'text-3xl' : 'text-6xl',
            )}
          >
            {degrees(last?.t2m_max_c)}
          </p>
          <p className="mt-1 text-[15px] font-medium">{t.temp_caption(formatShortDay(current.as_of))}</p>
        </div>
        <BigIcon className="size-16 shrink-0 animate-float-soft text-sun drop-shadow-lg" strokeWidth={1.5} aria-hidden="true" />
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2 text-center">
        {tiles.map(({ icon: Icon, value, label }) => (
          <div key={label} className="rounded-2xl bg-primary-foreground/15 px-1.5 py-2.5 backdrop-blur">
            <Icon className="mx-auto size-5" aria-hidden="true" />
            <p className="mt-1 text-sm leading-tight font-bold">{value}</p>
            <p className="text-xs leading-tight opacity-90">{label}</p>
          </div>
        ))}
      </div>

      {week.length > 0 && (
        <>
          {/* Titre visible : sans lui, ces jours passés se lisent comme des prévisions. */}
          <h3 className="mt-4 font-sans text-sm font-bold tracking-normal">{t.last_days}</h3>
          <ul className="mt-2 grid grid-cols-7 gap-1">
            {week.map((day) => {
              const rain = day.precip_mm !== null && day.precip_mm >= 1;
              const DayIcon = rain ? CloudRain : Sun;
              return (
                <li
                  key={day.date}
                  aria-label={t.day_label(
                    formatWeekday(day.date),
                    day.precip_mm === null ? fr.common.not_available : rain ? t.day_rain : t.day_dry,
                    degrees(day.t2m_max_c),
                  )}
                  className={cn(
                    'flex min-w-0 flex-col items-center gap-1 rounded-2xl py-2',
                    rain && 'bg-primary-foreground/20',
                  )}
                >
                  <span className="text-xs font-semibold opacity-90">{formatWeekday(day.date)}</span>
                  {day.precip_mm === null ? (
                    <span className="size-5" />
                  ) : (
                    <DayIcon className={cn('size-5', rain ? 'text-primary-foreground' : 'text-sun')} aria-hidden="true" />
                  )}
                  <span className="text-xs font-bold">{day.t2m_max_c === null ? '–' : degrees(day.t2m_max_c)}</span>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </section>
  );
}

/** Lien discret vers l'Espace technique : hors du parcours agriculteur, mais toujours atteignable. */
function TechnicalLink() {
  return (
    <div className="mx-5 mt-8 flex justify-center">
      <Link to="/technique" className="flex min-h-12 items-center px-3 text-sm font-semibold text-muted-foreground underline underline-offset-4">
        {t.technical_link}
      </Link>
    </div>
  );
}

function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <h2 className="text-lg font-bold">{children}</h2>
      {action}
    </div>
  );
}

export function HomePage() {
  const { activePlot, plotsLoading, plotsError, reloadPlots, analysis, analysisRunning, analysisError } = usePlot();
  const { profile, storageIssue } = useProfile();
  const advice = useAdvice();
  const season = useCurrentSeason();
  const clock = useAsync(() => api.getClock(), []);
  const cropSheets = useAsync(() => api.getCrops(), []);
  const [overlayHidden, setOverlayHidden] = useState(false);
  const [addingPlot, setAddingPlot] = useState(false);

  const current = activePlot && season.data?.plot_id === activePlot.plot_id ? season.data : null;
  const profileName = profile?.displayName || activePlot?.owner_name || '';
  const firstName = profileName.trim().split(/\s+/)[0] ?? '';
  const firstCritical = analysis?.prediction.critical_periods[0];
  const seasonFinalized = analysis !== null && analysis.season.status !== 'draft';
  const topCrops = analysis?.recommendation.top_3 ?? [];

  const startAdvice = () => {
    setOverlayHidden(false);
    void advice.start();
  };

  // Encart « À savoir » : alerte active des relevés, sinon première période à surveiller, sinon invitation.
  const activeAlert = current?.alerts.find((a) => a.active);
  const note = activeAlert?.message_fr ?? firstCritical?.message_fr ?? (analysis ? t.note_nothing : t.note_no_advice);

  // Ligne « culture · surface »
  const cropCode = activePlot ? lastCropCode(activePlot) : null;
  const cropName = cropCode ? cropSheets.data?.find((c) => c.code === cropCode)?.name_fr : t.no_crop;
  const area =
    activePlot && activePlot.area_ha !== null
      ? formatWithUnit(activePlot.area_ha, fr.units.ha, Number.isInteger(activePlot.area_ha) ? 0 : 1)
      : null;
  const cropLine = cropName && area ? t.crop_area(cropName, area) : (cropName ?? area);
  const status = plotStatus(current);

  return (
    <main className="flex-1 pb-6">
      <header className="flex items-center gap-3 px-5 pt-6">
        <Link
          to="/profil"
          aria-label={fr.profile.edit_action}
          className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-forest font-display font-bold text-primary-foreground"
        >
          {initials(profileName || fr.app.name)}
        </Link>
        <div className="min-w-0">
          <p className="text-[13px] font-medium text-muted-foreground">
            {clock.data
              ? `${capitalize(formatLongDay(clock.data.today))}${clock.data.is_overridden ? ` ${t.date_simulated}` : ''}`
              : clock.loading
                ? fr.common.loading
                : fr.common.not_available}
          </p>
          <h1 className="truncate font-display text-2xl leading-tight font-bold">
            {firstName ? t.greeting_name(firstName) : t.greeting}
          </h1>
          {profile?.village && (
            <p className="mt-1 flex items-center gap-1 text-sm font-medium text-muted-foreground">
              <MapPin className="size-4 shrink-0" aria-hidden="true" />
              <span className="truncate">{fr.profile.village_line(profile.village)}</span>
            </p>
          )}
        </div>
      </header>

      {storageIssue && (
        <p role="status" className="mx-5 mt-3 rounded-2xl bg-warning-soft p-3 text-sm font-medium text-foreground">
          {fr.profile.storage_issue}
        </p>
      )}

      {plotsLoading ? (
        <LoadingState variant="home" className="mx-5 mt-5" />
      ) : plotsError ? (
        <ErrorState error={plotsError} onRetry={reloadPlots} className="mx-5 mt-5" />
      ) : !activePlot ? (
        <section className="mx-5 mt-5 animate-fade-up">
          <EmptyState title={t.first_use_title} text={t.first_use_text}>
            <Button variant="hero" size="xl" onClick={() => setAddingPlot(true)}>
              <Map /> {fr.farm.add_plot}
            </Button>
          </EmptyState>
        </section>
      ) : (
        <>
          {/* 1. Action principale : obtenir les conseils, puis les voir. */}
          <section className="mx-5 mt-5 space-y-3">
            {seasonFinalized && analysis ? (
              <div className="rounded-3xl bg-card p-4 shadow-card">
                <div className="flex items-start gap-3">
                  <span className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-leaf-soft text-leaf-foreground">
                    {analysis.season.status === 'locked' ? <Lock className="size-6" /> : <CheckCircle2 className="size-6" />}
                  </span>
                  <div className="min-w-0">
                    <h2 className="font-display text-lg font-bold">
                      {analysis.season.status === 'locked' ? t.locked_title : t.closed_title}
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      {analysis.season.status === 'locked'
                        ? t.locked_text(analysis.season.season_label)
                        : t.closed_text(analysis.season.season_label)}
                    </p>
                  </div>
                </div>
                <ButtonLink to="/recommandation" variant="hero" size="lg" className="mt-3 w-full">
                  {t.locked_link} <ChevronRight />
                </ButtonLink>
              </div>
            ) : analysis ? (
              <>
                <Link to="/recommandation" className={buttonClasses({ variant: 'hero', size: 'xl' }, HERO)}>
                  <HeroContent
                    icon={Sprout}
                    title={fr.analyze.view}
                    subtitle={fr.analyze.view_subtitle(analysis.recommendation.main_crop.name_fr)}
                  />
                </Link>
                {/* L'actualisation reste possible, en action secondaire. */}
                <Button
                  variant="outline"
                  className="w-full"
                  disabled={analysisRunning}
                  aria-busy={analysisRunning}
                  onClick={startAdvice}
                >
                  {analysisRunning ? <Loader2 className="animate-spin" /> : <RefreshCw />}
                  {analysisRunning ? fr.analyze.running : fr.analyze.again}
                </Button>
              </>
            ) : (
              <Button
                variant="hero"
                size="xl"
                className={HERO}
                disabled={analysisRunning}
                aria-busy={analysisRunning}
                onClick={startAdvice}
              >
                <HeroContent
                  icon={analysisRunning ? Loader2 : ScanLine}
                  spin={analysisRunning}
                  title={analysisRunning ? fr.analyze.running : fr.analyze.button}
                  subtitle={analysisRunning ? fr.analyze.running_hint : fr.analyze.subtitle}
                />
              </Button>
            )}
            {analysisError && !analysisRunning && <ErrorState error={analysisError} />}
          </section>

          {/* 2. L'essentiel des conseils, dès qu'ils existent. */}
          {firstCritical && (
            <Link
              to="/prediction"
              className="mx-5 mt-4 flex items-center gap-3 rounded-3xl border border-warning/30 bg-warning-soft p-4 transition active:scale-[0.98]"
            >
              <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-warning text-primary-foreground">
                <AlertTriangle className="size-5" aria-hidden="true" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-[15px] font-bold text-foreground">{fr.critical.kind[firstCritical.kind]}</span>
                <span className="block text-sm text-muted-foreground">
                  {t.alert_sub(formatMonthYear(firstCritical.period))}
                </span>
              </span>
              <ChevronRight className="size-5 shrink-0 text-muted-foreground" aria-hidden="true" />
            </Link>
          )}

          {analysis && (
            <section className="mx-5 mt-6">
              <SectionTitle>{t.crops_title}</SectionTitle>
              {topCrops.length === 0 ? (
                <p className="rounded-3xl bg-card p-4 text-sm font-medium text-muted-foreground shadow-soft">{t.crops_none}</p>
              ) : (
                <>
                  <ul className="grid grid-cols-3 gap-2">
                    {topCrops.map((crop) => {
                      const level = suitability(crop.score);
                      return (
                        <li key={crop.crop_code} className="min-w-0">
                          <Link
                            to="/recommandation"
                            className="block overflow-hidden rounded-2xl bg-card shadow-soft transition active:scale-[0.97]"
                          >
                            <div className="relative h-16">
                              <CropThumb cropCode={crop.crop_code} alt="" className="size-full" />
                              <div className="absolute top-1 right-1 flex rounded-full bg-card p-0.5 shadow-soft">
                                <ScoreRing value={crop.score} tone={level.tone} size={36} />
                              </div>
                            </div>
                            <div className="p-2">
                              <p className="truncate font-display text-sm font-bold">{crop.name_fr}</p>
                              <p className="truncate text-xs font-semibold text-muted-foreground">{level.label}</p>
                            </div>
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                  {topCrops.some((crop) => hasCropImage(crop.crop_code)) && (
                    <p className="mt-2 text-xs font-medium text-muted-foreground">{t.crops_illustrations}</p>
                  )}
                </>
              )}
            </section>
          )}

          {/* 3. Relevés météo des jours passés. */}
          {season.error ? (
            <ErrorState error={season.error} onRetry={season.reload} className="mx-5 mt-5" />
          ) : current ? (
            <WeatherCard plot={activePlot} current={current} />
          ) : (
            <LoadingState variant="weather" className="mx-5 mt-5" />
          )}

          {/* 4. Champ actif. */}
          <section className="mx-5 mt-6 animate-fade-up [animation-delay:80ms]">
            <SectionTitle
              action={
                <Link to="/parcelle" className="flex min-h-12 items-center text-sm font-semibold text-primary">
                  {t.change_plot} <ChevronRight className="size-4" aria-hidden="true" />
                </Link>
              }
            >
              {t.active_plot}
            </SectionTitle>
            <article className="overflow-hidden rounded-3xl bg-card shadow-card">
              <div className="relative h-32">
                <PlotThumb plot={activePlot} alt={t.plot_illustration} className="absolute inset-0 size-full" />
                <div className="absolute inset-0 bg-gradient-fade" />
                {!season.loading && !season.error && (
                  <span
                    className={cn(
                      'absolute top-3 left-3 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold',
                      STATUS_CHIP[status].chip,
                    )}
                  >
                    <span className={cn('size-2 rounded-full', STATUS_CHIP[status].dot)} />
                    {fr.plot_status[status]}
                  </span>
                )}
                {hasPlotImage(activePlot) && <IllustrationTag className="top-3 right-3" />}
                <div className="absolute right-4 bottom-3 left-4 text-primary-foreground">
                  <h3 className="truncate font-display text-2xl font-bold">{activePlot.name}</h3>
                  {cropLine && <p className="truncate text-sm font-medium opacity-90">{cropLine}</p>}
                </div>
              </div>
              <div className="space-y-3 p-4">
                <p className="text-sm font-medium text-muted-foreground">{t.soil_line(fr.soil[activePlot.soil_texture])}</p>
                <div className="flex items-start gap-3 rounded-2xl bg-sun-soft p-3">
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-sun text-sun-foreground">
                    <Info className="size-5" aria-hidden="true" />
                  </span>
                  <p className="text-sm leading-snug font-medium text-foreground">
                    <span className="font-bold">{t.note}</span> {note}
                  </p>
                </div>
              </div>
            </article>
          </section>

          {analysisRunning && !overlayHidden && (
            <AnalysisOverlay plot={activePlot} onHide={() => setOverlayHidden(true)} />
          )}
        </>
      )}

      <TechnicalLink />

      <AddPlotSheet open={addingPlot} onClose={() => setAddingPlot(false)} onCreated={() => setAddingPlot(false)} />
    </main>
  );
}
