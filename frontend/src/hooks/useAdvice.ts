import { useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';
import { toast } from 'sonner';
import { usePlot } from '../context/PlotContext';
import { fr } from '../i18n/fr';

const ANNOUNCE_DELAY_MS = 350;

/**
 * « Obtenir mes conseils » : lance la préparation des conseils du champ actif (appel d'analyse),
 * annonce la fin, puis ouvre l'écran Cultures — la réponse d'abord.
 * Si l'utilisateur a quitté l'écran entre-temps, il n'est pas déplacé : seule l'annonce s'affiche.
 */
export function useAdvice() {
  const navigate = useNavigate();
  const { activePlot, runAnalysis, analysisRunning } = usePlot();

  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const start = useCallback(async () => {
    if (!activePlot) return;
    const plotName = activePlot.name;
    const result = await runAnalysis();
    if (!result) return;
    const announce = () =>
      toast.success(fr.analyze.done, {
        description: fr.analyze.done_text(
          plotName,
          result.prediction.critical_periods.length,
          result.recommendation.top_3.length,
        ),
      });
    if (mounted.current) {
      navigate('/recommandation');
      // Les notifications sont retirées à chaque changement d'écran (AppShell) :
      // celle-ci est donc affichée une fois l'écran Cultures en place.
      window.setTimeout(announce, ANNOUNCE_DELAY_MS);
    } else {
      announce();
    }
  }, [activePlot, runAnalysis, navigate]);

  return { start, running: analysisRunning };
}
