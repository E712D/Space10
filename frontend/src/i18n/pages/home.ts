/** Chaînes de l'écran « Accueil » (route /). */
export const home = {
  greeting: 'Bonjour',
  greeting_name: (firstName: string) => `Bonjour, ${firstName}`,
  date_simulated: '(date simulée)',
  first_use_title: 'Vos conseils agricoles, simplement',
  first_use_text: 'S3A vous aide à connaître la météo, les risques et les cultures adaptées près de chez vous.',

  // Carte météo : ce sont des relevés des jours passés, pas des prévisions.
  weather_title: 'Météo relevée',
  degrees: (value: string) => `${value}°`,
  temp_caption: (day: string) => `Température maximale · relevé du ${day}`,
  rain_7d: 'Pluie sur 7 jours',
  soil_moisture: 'Humidité du sol',
  soil_trend: 'Sol sur 7 jours',
  trend_up: 'En hausse',
  trend_down: 'En baisse',
  trend_stable: 'Stable',
  last_days: 'Les 7 derniers jours',
  day_rain: 'pluie',
  day_dry: 'pas de pluie',
  day_label: (day: string, weather: string, temp: string) => `${day} : ${weather}, ${temp}`,

  // Champ actif
  active_plot: 'Mon champ',
  change_plot: 'Changer',
  plot_illustration: 'Illustration d’un champ, ce n’est pas une photo de votre champ',
  no_crop: 'Aucune culture',
  crop_area: (crop: string, area: string) => `${crop} · ${area}`,
  soil_line: (soil: string) => `Sol : ${soil}`,
  note: 'À savoir :',
  note_no_advice: 'appuyez sur « Obtenir mes conseils » pour savoir quoi planter.',
  note_nothing: 'rien de particulier pour le moment.',

  // Décision verrouillée
  locked_title: 'Décision verrouillée',
  locked_text: (season: string) => `Le conseil de la saison ${season} est gardé. Il ne sera plus actualisé.`,
  closed_title: 'Saison terminée',
  closed_text: (season: string) => `La saison ${season} est terminée.`,
  locked_link: 'Voir ma décision',

  // Alerte
  alert_sub: (month: string) => `${month} · voir quoi surveiller`,

  // Cultures conseillées
  crops_title: 'Cultures conseillées',
  crops_none: 'Aucune culture conseillée pour ce champ.',
  crops_illustrations: 'Les images sont des illustrations.',

  technical_link: 'Espace technique (équipe S3A)',
} as const;
