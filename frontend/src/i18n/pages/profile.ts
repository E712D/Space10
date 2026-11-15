/** Chaînes de l'écran de profil local (sans authentification). */
export const profile = {
  eyebrow: 'Avant de commencer',
  title: 'Votre profil',
  intro: 'Quelques informations pour personnaliser S3A sur ce téléphone.',
  name_label: 'Comment vous appeler ?',
  name_placeholder: 'Votre prénom ou votre nom',
  name_required: 'Écrivez le nom à afficher pour continuer.',
  village_label: 'Votre village ou commune (facultatif)',
  village_placeholder: 'Ex. : Anyama',
  location_title: 'Position GPS (facultative)',
  location_text:
    'Votre position reste sur ce téléphone. Pour le moment, la météo affichée concerne le champ sélectionné, pas votre position GPS.',
  location_use: 'Utiliser ma position actuelle',
  location_refresh: 'Actualiser ma position',
  location_loading: 'Recherche de votre position…',
  location_saved: 'Position trouvée. Elle sera enregistrée avec votre profil.',
  location_remove: 'Retirer la position',
  location_denied: 'Accès refusé. Vous pouvez continuer sans partager votre position.',
  location_unavailable: 'Position indisponible. Réessayez ou continuez sans GPS.',
  location_timeout: 'La recherche prend trop de temps. Réessayez ou continuez sans GPS.',
  location_unsupported: 'Ce téléphone ne peut pas donner sa position. Vous pouvez continuer sans GPS.',
  location_error: 'Impossible de trouver votre position. Vous pouvez continuer sans GPS.',
  privacy_title: 'Pas de mot de passe',
  privacy_text:
    'Ce profil n’est pas un compte. Votre nom, votre village et votre position facultative sont enregistrés uniquement sur ce téléphone.',
  save: 'Continuer',
  save_edit: 'Enregistrer mon profil',
  cancel: 'Retour à l’accueil',
  edit_action: 'Modifier mon profil',
  village_line: (village: string) => `Village : ${village}`,
  storage_issue:
    'Le téléphone ne permet pas de lire ou garder le profil. Vous pouvez continuer, mais il faudra peut-être le saisir à nouveau.',
} as const;
