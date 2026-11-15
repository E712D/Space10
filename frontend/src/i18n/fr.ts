/**
 * Dictionnaire français : TOUTES les chaînes affichées par l'interface.
 * - Ce fichier : chaînes partagées (coque, navigation, états, unités…).
 * - ./pages/*.ts : chaînes propres à chaque écran.
 * Les textes venant de l'API (messages, raisons, bilan) ne sont pas ici.
 *
 * Vocabulaire (un seul mot par chose) : « champ » (jamais parcelle ni ferme),
 * « conseils » (jamais analyse), « Demander conseil » (assistant vocal).
 */
import { assistant } from './pages/assistant';
import { climate } from './pages/climate';
import { crops } from './pages/crops';
import { farm } from './pages/farm';
import { home } from './pages/home';
import { profile } from './pages/profile';
import { technical } from './pages/technical';

export const fr = {
  app: {
    name: 'S3A',
    subtitle: 'Assistant agricole',
    splash_tagline: 'Des conseils simples pour votre champ',
    splash_label: 'Ouverture de S3A',
    mock_banner: 'Démonstration : les données affichées sont simulées',
    offline_banner: 'Hors ligne : vérifiez votre connexion',
    illustration: 'Illustration',
    // Panneau de présentation (écran large uniquement)
    concept_eyebrow: 'NASA Space Apps Challenge · Abidjan 2026',
    concept_title: 'L’agriculture intelligente, dans la poche de chaque producteur.',
    concept_text:
      'S3A transforme les données satellites et climatiques en conseils simples, en français, pour les petits producteurs de Côte d’Ivoire et d’Afrique.',
    concept_chips: ['Données NASA POWER', 'Pensé pour les producteurs', 'Conseils parlés en français'],
  },
  nav: {
    label: 'Navigation principale',
    home: 'Accueil',
    home_desc: 'Vos conseils en un coup d’œil',
    farm: 'Mes champs',
    farm_desc: 'Vos champs et l’ajout guidé',
    talk: 'Demander conseil',
    talk_desc: 'Posez votre question à voix haute',
    climate: 'Climat',
    climate_desc: 'Pluie, chaleur, humidité du sol',
    crops: 'Cultures',
    crops_desc: 'La culture conseillée et pourquoi',
    technical: 'Espace technique',
    technical_desc: 'Modèles, système, apprentissage',
  },
  common: {
    loading: 'Chargement…',
    retry: 'Réessayer',
    not_available: 'Non disponible',
    error_title: 'Un problème est survenu',
    cancel: 'Annuler',
    close: 'Fermer',
    back: 'Retour',
    continue: 'Continuer',
    listen: 'Écouter',
    stop: 'Arrêter',
    speech_unavailable: 'La lecture vocale n’est pas disponible sur ce téléphone.',
    season: (label: string) => `Saison ${label}`,
    from_to: (start: string, end: string) => `Du ${start} au ${end}`,
    range: (low: string, high: string) => `entre ${low} et ${high}`,
    score: (n: string) => `Note ${n} sur 100`,
    no_plot_title: 'Votre champ n’est pas encore enregistré',
    no_plot_text: 'Ajoutez votre champ pour recevoir des conseils adaptés à votre région.',
    no_analysis_title: 'Pas encore de conseils',
    no_analysis_text: 'Appuyez sur le bouton pour préparer les conseils de votre champ.',
    locked: 'Verrouillée',
    draft: 'Modifiable',
    closed: 'Terminée',
  },
  quality: {
    observed: 'Mesuré',
    estimated: 'Estimé',
    needs_local_validation: 'À vérifier sur place',
    missing: 'Non disponible',
  },
  units: {
    mm: 'mm',
    celsius: '°C',
    days: 'j',
    ha: 'ha',
    pct: '%',
  },
  errors: {
    network: 'Impossible de joindre le serveur. Vérifiez votre connexion.',
    timeout: 'Le serveur met trop de temps à répondre. Réessayez dans un instant.',
    unknown: 'Erreur inattendue. Réessayez.',
  },
  /** Préparation des conseils (appel d'analyse du serveur). */
  analyze: {
    button: 'Obtenir mes conseils',
    subtitle: 'Appuyez ici pour préparer les conseils de votre champ',
    view: 'Voir mes conseils',
    view_subtitle: (crop: string) => `Culture conseillée : ${crop}`,
    again: 'Actualiser mes conseils',
    running: 'Préparation de vos conseils…',
    running_hint: 'Cela peut prendre une minute.',
    steps_title: 'Ce que nous faisons',
    steps: ['Regarder la météo de votre région', 'Repérer les périodes à surveiller', 'Chercher les cultures adaptées'],
    hide: 'Continuer à naviguer',
    done: 'Vos conseils sont prêts',
    done_text: (plot: string, alerts: number, crops: number) =>
      `${plot} : ${alerts} période${alerts > 1 ? 's' : ''} à surveiller, ${crops} culture${crops > 1 ? 's' : ''} conseillée${crops > 1 ? 's' : ''}.`,
  },
  soil: {
    sandy: 'Sableux',
    loamy: 'Limoneux',
    clay: 'Argileux',
    sandy_loam: 'Sablo-limoneux',
    clay_loam: 'Argilo-limoneux',
    unknown: 'Je ne sais pas',
  },
  soil_hints: {
    sandy: 'Clair, coule entre les doigts',
    loamy: 'Doux, sombre, se tient un peu',
    clay: 'Collant, lourd quand il pleut',
    sandy_loam: 'Granuleux mais se tient',
    clay_loam: 'Ferme, se fend quand il sèche',
    unknown: 'On fera sans pour l’instant',
  },
  /** Niveau d'adaptation d'une culture, d'après sa note sur 100 (seuils à valider par l'équipe agronomique). */
  suitability: {
    very: 'Très adaptée',
    good: 'Adaptée',
    possible: 'Possible',
  },
  plot_status: {
    ok: 'Rien à signaler',
    watch: 'À surveiller',
    unknown: 'Pas encore de relevé',
  },
  critical: {
    kind: {
      water_stress: 'Manque d’eau',
      erosion: 'Risque d’érosion',
      heat_stress: 'Forte chaleur',
      heavy_rain: 'Fortes pluies',
    },
    severity: { moderate: 'Risque modéré', high: 'Risque élevé' },
  },
  targets: {
    precip_mm: 'Pluie',
    t2m_max_c: 'Température maximale',
    sm_root: 'Humidité du sol',
  } as Record<string, string>,
  not_found: {
    title: 'Page introuvable',
    text: 'Cette page n’existe pas ou a été déplacée.',
    back: 'Retour à l’accueil',
  },
  home,
  profile,
  farm,
  climate,
  crops,
  assistant,
  technical,
} as const;
