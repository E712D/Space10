/** Chaînes de l'écran « Cultures » (route /recommandation). */
export const crops = {
  desired_title: 'Quelles cultures vous intéressent ?',
  desired_text:
    'Choisissez des cultures pour ce champ. Nous les comparerons aux conseils reçus. Ce choix n’est pas encore envoyé au calcul.',
  desired_legend: 'Cultures que vous souhaitez planter',
  desired_empty: 'Aucune culture n’est disponible pour le moment.',
  desired_results: 'Ce que disent les conseils',
  desired_not_evaluated:
    'Cette culture ne figure pas dans les résultats reçus. Elle n’a donc pas été évaluée ; cela ne signifie pas qu’elle est mauvaise.',
  desired_next_season: 'Conseillée pour la saison suivante',
  desired_penalty: (reason: string) => `Point à surveiller : ${reason}`,
  preference_storage_issue:
    'Le téléphone ne permet pas de garder ces choix. Ils resteront disponibles pendant cette visite, mais pourront être perdus ensuite.',

  // 1. Culture conseillée (toujours visible)
  main_title: 'Culture conseillée',
  why: 'Pourquoi ?',
  weak_points: 'Points faibles',
  listen: 'Écouter le conseil',
  stop: 'Arrêter la lecture',
  illustration_alt: (crop: string) => `Illustration : ${crop}`,
  illustrations_note: 'Les images sont des illustrations.',

  // 2. À surveiller (toujours visible)
  warnings_title: 'À surveiller',

  // 3. Détails repliés
  next_title: 'Pour la saison suivante',
  next_label: 'À planter ensuite',
  top_title: 'Les autres choix possibles',
  rank: (n: number) => `Choix numéro ${n}`,
  main_star: 'Culture conseillée',
  cover_title: 'Plantes de couverture',
  cover_hint: 'Elles protègent le sol et le nourrissent entre deux cultures.',
  missing_title: 'Informations manquantes',
  report_title: 'Lire le bilan écrit',
  report_version: (n: number) => `Version ${n}`,

  // 4. Décision
  decision_title: 'Ma décision',
  decision_text: 'Quand vous êtes prêt à planter, gardez ce conseil. Il ne changera plus pour cette saison.',
  auto_lock: (date: string) => `Il sera gardé automatiquement le ${date}.`,
  lock_button: 'Garder ce conseil',
  confirm_title: 'Garder ce conseil ?',
  confirm_text: (crop: string, season: string) =>
    `Le conseil « ${crop} » sera gardé pour la saison ${season}. Ensuite, il ne pourra plus être actualisé.`,
  confirm_yes: 'Oui, garder ce conseil',
  locking: 'Enregistrement…',
  lock_success: 'Conseil gardé',
  lock_success_text: 'Il ne changera plus pour cette saison.',
  locked_title: 'Décision verrouillée',
  locked_on: (date: string) => `Conseil gardé le ${date}.`,
  locked_text: 'Les conseils de cette saison ne changent plus.',
  closed_title: 'Saison terminée',
  closed_text: 'Cette saison est terminée.',
} as const;
