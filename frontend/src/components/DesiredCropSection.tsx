import { CheckCircle2 } from 'lucide-react';
import { useAsync } from '../hooks/useAsync';
import { formatNumber } from '../i18n/format';
import { fr } from '../i18n/fr';
import { suitability } from '../lib/visuals';
import { api } from '../services/api';
import type { AnalysisOut, CropScore } from '../types/api';
import { useCropPreferences } from '../context/CropPreferenceContext';
import { ErrorState, LoadingState } from './StateViews';

const t = fr.crops;

function resultFor(analysis: AnalysisOut | null, code: string): { crop: CropScore; future: boolean } | null {
  if (!analysis) return null;
  const current = [analysis.recommendation.main_crop, ...analysis.recommendation.top_3].find(
    (crop) => crop.crop_code === code,
  );
  if (current) return { crop: current, future: false };

  const next = analysis.recommendation.next_crop;
  return next?.crop_code === code ? { crop: next, future: true } : null;
}

export function DesiredCropSection({ analysis }: { analysis: AnalysisOut | null }) {
  const { desiredCrops, storageIssue, setDesiredCrops } = useCropPreferences();
  const crops = useAsync(() => api.getCrops(), []);

  return (
    <section className="mx-5 mb-5 rounded-3xl border border-border bg-card p-4 shadow-soft">
      <h2 className="font-display text-lg font-bold">{t.desired_title}</h2>
      <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{t.desired_text}</p>

      {storageIssue && (
        <p role="status" className="mt-3 rounded-2xl bg-warning-soft p-3 text-sm font-medium text-foreground">
          {t.preference_storage_issue}
        </p>
      )}

      {crops.loading ? (
        <LoadingState variant="crops" className="mt-3" />
      ) : crops.error ? (
        <ErrorState error={crops.error} onRetry={crops.reload} className="mt-3" />
      ) : !crops.data?.length ? (
        <p role="status" className="mt-3 rounded-2xl bg-muted p-3 text-sm text-muted-foreground">{t.desired_empty}</p>
      ) : (
        <fieldset className="mt-3">
          <legend className="sr-only">{t.desired_legend}</legend>
          <div className="grid grid-cols-2 gap-2">
            {crops.data.map((crop) => {
              const checked = desiredCrops.includes(crop.code);
              return (
                <label
                  key={crop.code}
                  className={`flex min-h-14 min-w-0 cursor-pointer items-center gap-2 rounded-2xl border-2 px-3 py-2 text-sm font-semibold transition-colors ${
                    checked ? 'border-leaf bg-leaf-soft text-leaf-foreground' : 'border-border bg-background'
                  }`}
                >
                  <input
                    type="checkbox"
                    className="size-5 shrink-0 accent-primary"
                    checked={checked}
                    onChange={() =>
                      setDesiredCrops(
                        checked ? desiredCrops.filter((code) => code !== crop.code) : [...desiredCrops, crop.code],
                      )
                    }
                  />
                  <span className="min-w-0 break-words">{crop.name_fr}</span>
                </label>
              );
            })}
          </div>
        </fieldset>
      )}

      {analysis && desiredCrops.length > 0 && (
        <div className="mt-4 space-y-2" aria-live="polite">
          <h3 className="text-sm font-bold">{t.desired_results}</h3>
          {desiredCrops.map((code) => {
            const result = resultFor(analysis, code);
            const name = crops.data?.find((crop) => crop.code === code)?.name_fr ?? code;
            if (!result) {
              return (
                <div key={code} className="rounded-2xl bg-muted p-3">
                  <p className="font-bold">{name}</p>
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{t.desired_not_evaluated}</p>
                </div>
              );
            }

            const level = suitability(result.crop.score);
            return (
              <div key={code} className="rounded-2xl bg-leaf-soft p-3 text-leaf-foreground">
                <p className="flex items-center gap-2 font-bold">
                  <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" />
                  <span>{name}</span>
                </p>
                <p className="mt-1 text-sm font-semibold">
                  {result.future ? t.desired_next_season : level.label} · {fr.common.score(formatNumber(result.crop.score, 0))}
                </p>
                {result.crop.reasons[0] && <p className="mt-1 text-sm leading-relaxed">{result.crop.reasons[0]}</p>}
                {result.crop.penalties[0] && (
                  <p className="mt-1 text-sm leading-relaxed">{t.desired_penalty(result.crop.penalties[0])}</p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
