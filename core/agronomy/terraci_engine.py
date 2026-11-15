import calendar
import csv
import math
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

GRID_METADATA = {
    "lat_max": 6.8500,       # Limite Nord
    "lon_min": -5.3200,      # Limite Ouest
    "resolution": 0.000269,  # Taille d'un pixel en degrés (~30m pour Landsat)
    "max_rows": 10,          # Réduit pour la démonstration (simulation 10x10)
    "max_cols": 10,
    "zone": "Bouaké",
}

# Paramètres expérimentaux des cultures; les valeurs quantitatives restent à valider localement.
CATALOGUE_CULTURES = {
    "manioc": {
        "pluie_min_saison_mm": 500,
        "temp_surface_max_c": 38.0,
        "famille": "euphorbiaceae",
        "gain_azote": 0.1,
        "couverture_sol": 0.4,
        "valeur_marche_xof": 400
    },
    "mais": {
        "pluie_min_saison_mm": 600,
        "temp_surface_max_c": 35.0,
        "famille": "poaceae",
        "gain_azote": -0.3,
        "couverture_sol": 0.6,
        "valeur_marche_xof": 600
    },
    "niebe": {
        "pluie_min_saison_mm": 300,
        "temp_surface_max_c": 41.0,
        "famille": "fabaceae",
        "gain_azote": 0.9,
        "couverture_sol": 0.8,
        "valeur_marche_xof": 800
    },
    "sorgho": {
        "pluie_min_saison_mm": 350,
        "temp_surface_max_c": 40.0,
        "famille": "poaceae",
        "gain_azote": 0.0,
        "couverture_sol": 0.5,
        "valeur_marche_xof": 500
    }
}

# Cultures observées à Bouaké; leur reconnaissance ne fournit aucun paramètre de score.
CULTURES_MARAICHERES_RECONNUES = {
    "aubergine": "Aubergine",
    "aubergine africaine": "Aubergine africaine",
    "aubergine africain": "Aubergine africaine",
    "aubergine violette": "Aubergine violette",
    "carotte": "Carotte",
    "carrote": "Carotte",
    "celerie": "Céleri",
    "chou": "Chou",
    "chou et haricot": "Association chou-haricot",
    "ciboulette": "Ciboulette",
    "concombre": "Concombre",
    "cougette": "Courgette",
    "courgette": "Courgette",
    "gombo": "Gombo",
    "haricot": "Haricot",
    "haricot vert": "Haricot vert",
    "haricots": "Haricots",
    "laitue": "Laitue",
    "oignon": "Oignon",
    "oignon +chou": "Association oignon-chou",
    "poireau": "Poireau",
    "poivron": "Poivron",
    "piment": "Piment",
    "tomate": "Tomate",
    "tomate;piment": "Association tomate-piment",
}

CONTEXTE_EMPIRIQUE_BOUAKE = (
    {
        "indicateur": "Producteurs enquêtés déclarant pratiquer la rotation",
        "valeur": 19,
        "unite": "%",
        "zone": "Sous-préfecture de Bouaké",
        "source": (
            "Mémoire de Master 2, Koffi Kouassi Jean Alexis, "
            "Université Alassane Ouattara, 2021-2022"
        ),
        "url_source": (
            "https://agritrop.cirad.fr/614401/1/"
            "M_moire%20Corrig_%20Koffi%20Jean%20Alexis%20version3.pdf"
        ),
        "statut_verification": "a_confirmer",
        "limite": (
            "Confirmer le dénominateur, la définition de rotation et le passage source "
            "avant de présenter ce pourcentage comme vérifié."
        ),
    },
    {
        "indicateur": "Précarité foncière et répétition des cycles sur les mêmes planches",
        "valeur": "constat qualitatif rapporté",
        "zone": "Site maraîcher CNPS-Bouaké",
        "effectif": 40,
        "unite_effectif": "chefs d'exploitation",
        "source": "Étude de Kra Kouakou Valentin sur le maraîchage intra-urbain",
        "url_source": (
            "https://www.nzassa-revue.net/admin/img/paper/"
            "31.%20KRA%20Kouakou%20Valentin.pdf"
        ),
        "statut_verification": "a_confirmer",
        "limite": (
            "Constat associé à un site et à un échantillon; ne pas généraliser à "
            "toutes les exploitations de Bouaké."
        ),
    },
    {
        "indicateur": "Séquences habituelles lisibles dans l'enquête MARIGO 2023",
        "valeur": 8,
        "unite": "séquences textuelles",
        "zone": "Bouaké",
        "effectif": 10,
        "effectif_total_fichier": 43,
        "source": (
            "Avadí, Dosso et Ouedraogo, Données techniques et socio-économiques "
            "des producteurs maraîchers dans 4 villes Ivoiriennes, 2023"
        ),
        "url_source": "https://doi.org/10.18167/DVN1/HG0DNY",
        "statut_verification": "descriptif_non_representatif",
        "limite": (
            "Décompte du classeur public data.xlsx : 10 lignes avec Ville=Bouaké sur "
            "43 lignes non vides; 8 champs de rotation sont des séquences lisibles et "
            "2 contiennent des codes numériques non interprétés. Pratiques déclarées, "
            "sans dates par parcelle ni résultats d'essai : ne pas en déduire une règle "
            "agronomique ni un taux représentatif."
        ),
    },
)


def _normaliser_nom_culture(nom):
    sans_accents = "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", nom.casefold())
        if not unicodedata.combining(caractere)
    )
    return " ".join(sans_accents.split())


# Poids des scénarios pour la notation multicritère (ce n'est pas un calcul AHP).
# Lignes : [Eau, Azote, Protection Érosion, Rendement Économique]
MATRICE_POIDS = {
    "temoin":       np.array([0.15, 0.15, 0.10, 0.60]),
    "hydrique":     np.array([0.50, 0.10, 0.10, 0.30]),
    "regeneration": np.array([0.10, 0.40, 0.30, 0.20])
}


def charger_nasa_power_csv(chemin_fichier):
    """Agrège l'export quotidien NASA POWER en observations mensuelles."""
    with open(chemin_fichier, newline="", encoding="utf-8-sig") as fichier:
        lignes = fichier.readlines()

    fin_entete = next(
        (index for index, ligne in enumerate(lignes) if ligne.strip() == "-END HEADER-"),
        None,
    )
    if fin_entete is None:
        raise ValueError("L'en-tête NASA POWER doit contenir '-END HEADER-'.")

    lecteur = csv.DictReader(lignes[fin_entete + 1:])
    if lecteur.fieldnames is None:
        raise ValueError("Le CSV NASA POWER ne contient pas de ligne de colonnes.")
    lecteur.fieldnames = [nom.strip() if nom else nom for nom in lecteur.fieldnames]
    colonnes_requises = {"YEAR", "DOY", "PRECTOTCORR", "T2M", "RH2M"}
    colonnes_manquantes = colonnes_requises - set(lecteur.fieldnames)
    if colonnes_manquantes:
        raise ValueError(
            "Colonnes NASA POWER manquantes : "
            + ", ".join(sorted(colonnes_manquantes))
            + "."
        )

    agregats = {}
    dates_vues = set()
    for ligne in lecteur:
        numero_ligne = fin_entete + 1 + lecteur.line_num
        if None in ligne:
            raise ValueError(f"Ligne {numero_ligne} : trop de valeurs dans le CSV.")
        try:
            annee = int(ligne["YEAR"])
            jour_annee = int(ligne["DOY"])
            date_debut_annee = date(annee, 1, 1)
            nombre_jours_annee = (date(annee, 12, 31) - date_debut_annee).days + 1
            if not 1 <= jour_annee <= nombre_jours_annee:
                raise ValueError("DOY hors de l'année indiquée.")
            jour = date_debut_annee + timedelta(days=jour_annee - 1)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(
                f"Ligne {numero_ligne} : YEAR ou DOY invalide."
            ) from exc

        if jour in dates_vues:
            raise ValueError(f"Ligne {numero_ligne} : date dupliquée ({jour}).")
        dates_vues.add(jour)

        cle = (jour.year, jour.month)
        mois = agregats.setdefault(
            cle,
            {
                "jours_donnees": 0,
                "pluie_mm": 0.0,
                "pluie_jours_valides": 0,
                "temperature_c": 0.0,
                "temperature_jours_valides": 0,
                "humidite_pct": 0.0,
                "humidite_jours_valides": 0,
            },
        )
        mois["jours_donnees"] += 1

        for colonne, total, compte in (
            ("PRECTOTCORR", "pluie_mm", "pluie_jours_valides"),
            ("T2M", "temperature_c", "temperature_jours_valides"),
            ("RH2M", "humidite_pct", "humidite_jours_valides"),
        ):
            try:
                valeur = float(ligne[colonne])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Ligne {numero_ligne} : valeur invalide pour {colonne}."
                ) from exc
            if not math.isfinite(valeur):
                raise ValueError(
                    f"Ligne {numero_ligne} : valeur non finie pour {colonne}."
                )
            if valeur == -999:
                continue
            if colonne == "PRECTOTCORR" and valeur < 0:
                raise ValueError(f"Ligne {numero_ligne} : pluie négative.")
            if colonne == "T2M" and not -90 <= valeur <= 70:
                raise ValueError(f"Ligne {numero_ligne} : T2M hors limites.")
            if colonne == "RH2M" and not 0 <= valeur <= 100:
                raise ValueError(f"Ligne {numero_ligne} : RH2M hors limites.")
            mois[total] += valeur
            mois[compte] += 1

    if not agregats:
        raise ValueError("Le CSV NASA POWER ne contient aucune observation quotidienne.")

    observations_mensuelles = []
    for (annee, numero_mois), valeurs in sorted(agregats.items()):
        jours_mois = calendar.monthrange(annee, numero_mois)[1]
        pluie_complete = (
            valeurs["jours_donnees"] == jours_mois
            and valeurs["pluie_jours_valides"] == jours_mois
        )
        observations_mensuelles.append(
            {
                "annee": annee,
                "mois": numero_mois,
                "jours_donnees": valeurs["jours_donnees"],
                "jours_dans_le_mois": jours_mois,
                "pluie_mensuelle_mm": (
                    round(valeurs["pluie_mm"], 2) if pluie_complete else None
                ),
                "pluie_jours_valides": valeurs["pluie_jours_valides"],
                "temperature_air_2m_moyenne_c": (
                    round(
                        valeurs["temperature_c"]
                        / valeurs["temperature_jours_valides"],
                        2,
                    )
                    if valeurs["temperature_jours_valides"]
                    else None
                ),
                "temperature_jours_valides": valeurs["temperature_jours_valides"],
                "humidite_relative_2m_moyenne_pct": (
                    round(
                        valeurs["humidite_pct"]
                        / valeurs["humidite_jours_valides"],
                        2,
                    )
                    if valeurs["humidite_jours_valides"]
                    else None
                ),
                "humidite_jours_valides": valeurs["humidite_jours_valides"],
            }
        )
    return observations_mensuelles


def charger_nasa_power_pluie_quotidienne(chemin_fichier):
    """Lit les précipitations journalières NASA POWER sans transformer les manquants en zéros."""
    with open(chemin_fichier, newline="", encoding="utf-8-sig") as fichier:
        lignes = fichier.readlines()

    fin_entete = next(
        (index for index, ligne in enumerate(lignes) if ligne.strip() == "-END HEADER-"),
        None,
    )
    if fin_entete is None:
        raise ValueError("L'en-tête NASA POWER doit contenir '-END HEADER-'.")

    lecteur = csv.DictReader(lignes[fin_entete + 1:])
    if lecteur.fieldnames is None:
        raise ValueError("Le CSV NASA POWER ne contient pas de ligne de colonnes.")
    lecteur.fieldnames = [nom.strip() if nom else nom for nom in lecteur.fieldnames]
    colonnes_requises = {"YEAR", "DOY", "PRECTOTCORR"}
    colonnes_manquantes = colonnes_requises - set(lecteur.fieldnames)
    if colonnes_manquantes:
        raise ValueError(
            "Colonnes NASA POWER manquantes : "
            + ", ".join(sorted(colonnes_manquantes))
            + "."
        )

    observations = []
    dates_vues = set()
    for ligne in lecteur:
        numero_ligne = fin_entete + 1 + lecteur.line_num
        if None in ligne:
            raise ValueError(f"Ligne {numero_ligne} : trop de valeurs dans le CSV.")
        try:
            annee = int(ligne["YEAR"])
            jour_annee = int(ligne["DOY"])
            debut_annee = date(annee, 1, 1)
            nombre_jours = (date(annee, 12, 31) - debut_annee).days + 1
            if not 1 <= jour_annee <= nombre_jours:
                raise ValueError("DOY hors de l'année indiquée.")
            jour = debut_annee + timedelta(days=jour_annee - 1)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(
                f"Ligne {numero_ligne} : YEAR ou DOY invalide."
            ) from exc

        if jour in dates_vues:
            raise ValueError(f"Ligne {numero_ligne} : date dupliquée ({jour}).")
        dates_vues.add(jour)

        try:
            pluie = float(ligne["PRECTOTCORR"])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Ligne {numero_ligne} : valeur invalide pour PRECTOTCORR."
            ) from exc
        if not math.isfinite(pluie):
            raise ValueError(
                f"Ligne {numero_ligne} : valeur non finie pour PRECTOTCORR."
            )
        if pluie != -999 and pluie < 0:
            raise ValueError(f"Ligne {numero_ligne} : pluie négative.")

        observations.append(
            {
                "date": jour.isoformat(),
                "pluie_mm": None if pluie == -999 else pluie,
            }
        )

    if not observations:
        raise ValueError("Le CSV NASA POWER ne contient aucune observation quotidienne.")
    return observations


def comparer_cumuls_pluie_par_periode(observations_mensuelles, periodes=None):
    """Compare les cumuls de pluie par annee pour des listes de mois."""
    if not isinstance(observations_mensuelles, (list, tuple)):
        raise TypeError("observations_mensuelles doit être une liste ou un tuple.")
    if periodes is None:
        periodes = {
            "avril_juillet": (4, 5, 6, 7),
            "aout_novembre": (8, 9, 10, 11),
        }
    if not isinstance(periodes, dict) or not periodes:
        raise ValueError("periodes doit être un dictionnaire non vide.")

    pluie_par_mois = {}
    for observation in observations_mensuelles:
        if not isinstance(observation, dict):
            raise TypeError("Chaque observation mensuelle doit être un dictionnaire.")
        annee = observation.get("annee")
        mois = observation.get("mois")
        pluie = observation.get("pluie_mensuelle_mm")
        if type(annee) is not int or annee < 1:
            raise ValueError("Chaque observation doit avoir une année valide.")
        if type(mois) is not int or not 1 <= mois <= 12:
            raise ValueError("Chaque observation doit avoir un mois de 1 à 12.")
        if pluie is not None:
            try:
                pluie = float(pluie)
            except (TypeError, ValueError) as exc:
                raise ValueError("Le cumul mensuel de pluie doit être numérique ou None.") from exc
            if not math.isfinite(pluie) or pluie < 0:
                raise ValueError("Le cumul mensuel de pluie doit être fini et positif ou nul.")
        cle = (annee, mois)
        if cle in pluie_par_mois:
            raise ValueError(f"Observation mensuelle dupliquée pour {annee}-{mois:02d}.")
        pluie_par_mois[cle] = pluie

    if not pluie_par_mois:
        raise ValueError("Aucune observation mensuelle à comparer.")

    annees = sorted({annee for annee, _ in pluie_par_mois})
    resultats = {}
    for nom, mois_periode in periodes.items():
        if not isinstance(nom, str) or not nom.strip():
            raise ValueError("Chaque période doit avoir un nom textuel non vide.")
        if (
            not isinstance(mois_periode, (list, tuple))
            or not mois_periode
            or any(type(mois) is not int or not 1 <= mois <= 12 for mois in mois_periode)
            or len(set(mois_periode)) != len(mois_periode)
        ):
            raise ValueError(
                f"La période {nom!r} doit contenir des numéros de mois uniques de 1 à 12."
            )

        cumuls_par_annee = {}
        for annee in annees:
            cumuls_mensuels = [
                pluie_par_mois.get((annee, mois)) for mois in mois_periode
            ]
            if any(pluie is None for pluie in cumuls_mensuels):
                cumuls_par_annee[annee] = None
            else:
                cumuls_complets_mensuels = [
                    pluie for pluie in cumuls_mensuels if pluie is not None
                ]
                cumuls_par_annee[annee] = round(sum(cumuls_complets_mensuels), 1)

        cumuls_complets = [
            cumul for cumul in cumuls_par_annee.values() if cumul is not None
        ]
        resultats[nom] = {
            "mois": list(mois_periode),
            "cumuls_par_annee_mm": cumuls_par_annee,
            "nombre_annees_completes": len(cumuls_complets),
            "moyenne_mm": (
                round(sum(cumuls_complets) / len(cumuls_complets), 1)
                if cumuls_complets
                else None
            ),
            "minimum_mm": min(cumuls_complets) if cumuls_complets else None,
            "maximum_mm": max(cumuls_complets) if cumuls_complets else None,
        }
    return resultats


def _valider_valeur_humidite_smap(valeur, nom_variable):
    if isinstance(valeur, bool):
        raise TypeError(f"{nom_variable} doit être une valeur numérique.")
    try:
        valeur = float(valeur)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{nom_variable} doit être numérique ou None.") from exc
    if not math.isfinite(valeur) or not 0 <= valeur <= 0.9:
        raise ValueError(f"{nom_variable} doit être fini et compris entre 0 et 0,9.")
    return valeur


def _valider_coord_smap(valeur, nom_variable, minimum, maximum):
    if isinstance(valeur, bool):
        raise TypeError(f"{nom_variable} doit être une coordonnée numérique.")
    try:
        valeur = float(valeur)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{nom_variable} doit être une coordonnée numérique.") from exc
    if not math.isfinite(valeur) or not minimum <= valeur <= maximum:
        raise ValueError(f"{nom_variable} est hors limites.")
    return valeur


def _lire_scalaire_smap(fichier_nc, nom_variable, nom_fichier):
    variable = fichier_nc.get(nom_variable)
    if variable is None:
        raise ValueError(f"{nom_fichier} : variable SMAP manquante ({nom_variable}).")
    valeurs = np.asarray(variable[...], dtype=float)
    if valeurs.size != 1:
        raise ValueError(
            f"{nom_fichier} : {nom_variable} doit contenir exactement une cellule."
        )
    return float(valeurs.reshape(-1)[0])


def _lire_valeur_humidite_smap(fichier_nc, chemin_variable, nom_variable, nom_fichier):
    variable = fichier_nc.get(chemin_variable)
    if variable is None:
        raise ValueError(f"{nom_fichier} : variable SMAP manquante ({chemin_variable}).")

    unites = variable.attrs.get("units")
    if isinstance(unites, bytes):
        unites = unites.decode("utf-8")
    if unites != "m3 m-3":
        raise ValueError(
            f"{nom_fichier} : unités inattendues pour {nom_variable} ({unites!r})."
        )

    valeurs = np.asarray(variable[...], dtype=float)
    if valeurs.size != 1:
        raise ValueError(
            f"{nom_fichier} : {nom_variable} doit contenir exactement une cellule."
        )
    valeur = float(valeurs.reshape(-1)[0])

    sentinelles = [
        float(np.asarray(variable.attrs[attribut]).reshape(-1)[0])
        for attribut in ("_FillValue", "missing_value", "fmissing_value")
        if attribut in variable.attrs
    ]
    if math.isnan(valeur) and any(math.isnan(s) for s in sentinelles):
        return None
    if not math.isfinite(valeur):
        raise ValueError(f"{nom_fichier} : valeur non finie pour {nom_variable}.")
    if any(valeur == sentinelle for sentinelle in sentinelles):
        return None

    valeur = _valider_valeur_humidite_smap(valeur, nom_variable)
    minimum_valide = float(variable.attrs.get("valid_min", 0.0))
    maximum_valide = float(variable.attrs.get("valid_max", 0.9))
    if not minimum_valide <= valeur <= maximum_valide:
        raise ValueError(f"{nom_fichier} : valeur hors limites pour {nom_variable}.")
    return valeur


def charger_smap_harmony_nc4(chemin):
    """Lit les fichiers Harmony SMAP pointés et conserve unités, cellule et provenance."""
    try:
        import h5py
    except ImportError as exc:
        raise RuntimeError(
            "La lecture des fichiers SMAP Harmony nécessite le paquet h5py."
        ) from exc

    chemin = Path(chemin)
    if chemin.is_file():
        fichiers = [chemin]
    elif chemin.is_dir():
        fichiers = sorted(chemin.glob("*.nc4"))
    else:
        raise FileNotFoundError(f"Chemin SMAP introuvable : {chemin}.")
    if not fichiers:
        raise ValueError(f"Aucun fichier NetCDF4 SMAP trouvé dans {chemin}.")
    if any(fichier.suffix.lower() != ".nc4" for fichier in fichiers):
        raise ValueError("Les fichiers SMAP Harmony doivent être au format .nc4.")

    observations = []
    dates_heures_vues = set()
    cellule_reference = None
    for fichier in fichiers:
        correspondance = re.search(r"(\d{8}T\d{6})", fichier.name)
        if correspondance is None:
            raise ValueError(
                f"{fichier.name} : horodatage SMAP absent du nom de fichier."
            )
        try:
            date_heure = datetime.strptime(
                correspondance.group(1), "%Y%m%dT%H%M%S"
            ).replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise ValueError(
                f"{fichier.name} : horodatage SMAP invalide."
            ) from exc
        if date_heure in dates_heures_vues:
            raise ValueError(
                f"Horodatage SMAP dupliqué : {date_heure.isoformat()}."
            )
        dates_heures_vues.add(date_heure)

        try:
            with h5py.File(fichier, "r") as fichier_nc:
                latitude = _lire_scalaire_smap(fichier_nc, "cell_lat", fichier.name)
                longitude = _lire_scalaire_smap(fichier_nc, "cell_lon", fichier.name)
                if (
                    not math.isfinite(latitude)
                    or not -90 <= latitude <= 90
                    or not math.isfinite(longitude)
                    or not -180 <= longitude <= 180
                ):
                    raise ValueError(
                        f"{fichier.name} : coordonnées de cellule SMAP invalides."
                    )

                cellule = (latitude, longitude)
                if cellule_reference is None:
                    cellule_reference = cellule
                elif not (
                    math.isclose(cellule[0], cellule_reference[0], abs_tol=1e-4)
                    and math.isclose(cellule[1], cellule_reference[1], abs_tol=1e-4)
                ):
                    raise ValueError(
                        "Les fichiers SMAP ne correspondent pas à la même cellule."
                    )

                observations.append(
                    {
                        "date_heure_utc": date_heure.isoformat(),
                        "sm_rootzone_m3_m3": _lire_valeur_humidite_smap(
                            fichier_nc,
                            "Geophysical_Data/sm_rootzone",
                            "sm_rootzone",
                            fichier.name,
                        ),
                        "sm_surface_m3_m3": _lire_valeur_humidite_smap(
                            fichier_nc,
                            "Geophysical_Data/sm_surface",
                            "sm_surface",
                            fichier.name,
                        ),
                        "latitude_cellule_deg": latitude,
                        "longitude_cellule_deg": longitude,
                        "fichier_source": fichier.name,
                    }
                )
        except OSError as exc:
            raise OSError(f"Impossible de lire le fichier SMAP {fichier}.") from exc

    return sorted(observations, key=lambda observation: observation["date_heure_utc"])


def agreger_smap_par_mois(observations):
    """Calcule les moyennes mensuelles SMAP sans présenter un mois incomplet comme complet."""
    if not isinstance(observations, (list, tuple)) or not observations:
        raise ValueError("observations SMAP doit être une liste non vide.")

    groupes = {}
    dates_heures_vues = set()
    cellule_reference = None
    for observation in observations:
        if not isinstance(observation, dict):
            raise TypeError("Chaque observation SMAP doit être un dictionnaire.")
        horodatage = observation.get("date_heure_utc")
        if not isinstance(horodatage, str):
            raise ValueError("Chaque observation SMAP doit avoir un horodatage UTC.")
        try:
            date_heure = datetime.fromisoformat(horodatage)
        except ValueError as exc:
            raise ValueError(f"Horodatage SMAP invalide : {horodatage!r}.") from exc
        if date_heure.tzinfo is None or date_heure.utcoffset() != timedelta(0):
            raise ValueError("Les horodatages SMAP doivent être explicitement en UTC.")
        if date_heure in dates_heures_vues:
            raise ValueError(
                f"Horodatage SMAP dupliqué : {date_heure.isoformat()}."
            )
        dates_heures_vues.add(date_heure)

        latitude = _valider_coord_smap(
            observation.get("latitude_cellule_deg"),
            "latitude_cellule_deg",
            -90,
            90,
        )
        longitude = _valider_coord_smap(
            observation.get("longitude_cellule_deg"),
            "longitude_cellule_deg",
            -180,
            180,
        )
        cellule = (latitude, longitude)
        if cellule_reference is None:
            cellule_reference = cellule
        elif not (
            math.isclose(cellule[0], cellule_reference[0], abs_tol=1e-4)
            and math.isclose(cellule[1], cellule_reference[1], abs_tol=1e-4)
        ):
            raise ValueError("Les observations SMAP ne correspondent pas à la même cellule.")

        cle = (date_heure.year, date_heure.month)
        groupe = groupes.setdefault(
            cle,
            {"dates_heures": set(), "sm_rootzone": [], "sm_surface": []},
        )
        groupe["dates_heures"].add(date_heure)
        for nom, champ in (
            ("sm_rootzone", "sm_rootzone_m3_m3"),
            ("sm_surface", "sm_surface_m3_m3"),
        ):
            valeur = observation.get(champ)
            if valeur is not None:
                groupe[nom].append(_valider_valeur_humidite_smap(valeur, champ))

    resultats = []
    for (annee, numero_mois), groupe in sorted(groupes.items()):
        jours_mois = calendar.monthrange(annee, numero_mois)[1]
        # Les fichiers SMAP 3 h sont horodatés au milieu de chaque intervalle.
        debut = datetime(annee, numero_mois, 1, 1, 30, tzinfo=timezone.utc)
        dates_heures_attendues = set()
        while debut.month == numero_mois:
            dates_heures_attendues.add(debut)
            debut += timedelta(hours=3)

        couverture_complete = groupe["dates_heures"] == dates_heures_attendues
        resultat = {
            "annee": annee,
            "mois": numero_mois,
            "observations_3h_recues": len(groupe["dates_heures"]),
            "observations_3h_attendues": jours_mois * 8,
            "couverture_complete": couverture_complete,
        }
        for nom in ("sm_rootzone", "sm_surface"):
            valeurs = groupe[nom]
            moyenne_partielle = (
                round(sum(valeurs) / len(valeurs), 6) if valeurs else None
            )
            moyenne_complete = (
                moyenne_partielle
                if couverture_complete
                and len(valeurs) == len(dates_heures_attendues)
                else None
            )
            resultat[f"{nom}_m3_m3_observations_valides"] = len(valeurs)
            resultat[f"{nom}_m3_m3_moyenne_partielle"] = moyenne_partielle
            resultat[f"{nom}_m3_m3_moyenne"] = moyenne_complete
        resultats.append(resultat)
    return resultats


def agreger_smap_par_jour(observations):
    """Calcule les moyennes journalières SMAP et signale les journées incomplètes."""
    if not isinstance(observations, (list, tuple)) or not observations:
        raise ValueError("observations SMAP doit être une liste non vide.")

    groupes = {}
    dates_heures_vues = set()
    cellule_reference = None
    for observation in observations:
        if not isinstance(observation, dict):
            raise TypeError("Chaque observation SMAP doit être un dictionnaire.")
        horodatage = observation.get("date_heure_utc")
        if not isinstance(horodatage, str):
            raise ValueError("Chaque observation SMAP doit avoir un horodatage UTC.")
        try:
            date_heure = datetime.fromisoformat(horodatage)
        except ValueError as exc:
            raise ValueError(f"Horodatage SMAP invalide : {horodatage!r}.") from exc
        if date_heure.tzinfo is None or date_heure.utcoffset() != timedelta(0):
            raise ValueError("Les horodatages SMAP doivent être explicitement en UTC.")
        debut_journee = datetime(
            date_heure.year, date_heure.month, date_heure.day, 1, 30,
            tzinfo=timezone.utc,
        )
        if (
            date_heure < debut_journee
            or (date_heure - debut_journee).total_seconds() % (3 * 60 * 60) != 0
        ):
            raise ValueError(
                "Les horodatages SMAP doivent suivre le pas de 3 h attendu."
            )
        if date_heure in dates_heures_vues:
            raise ValueError(
                f"Horodatage SMAP dupliqué : {date_heure.isoformat()}."
            )
        dates_heures_vues.add(date_heure)

        latitude = _valider_coord_smap(
            observation.get("latitude_cellule_deg"),
            "latitude_cellule_deg",
            -90,
            90,
        )
        longitude = _valider_coord_smap(
            observation.get("longitude_cellule_deg"),
            "longitude_cellule_deg",
            -180,
            180,
        )
        cellule = (latitude, longitude)
        if cellule_reference is None:
            cellule_reference = cellule
        elif not (
            math.isclose(cellule[0], cellule_reference[0], abs_tol=1e-4)
            and math.isclose(cellule[1], cellule_reference[1], abs_tol=1e-4)
        ):
            raise ValueError("Les observations SMAP ne correspondent pas à la même cellule.")

        groupe = groupes.setdefault(
            date_heure.date(),
            {"dates_heures": set(), "sm_rootzone": [], "sm_surface": []},
        )
        groupe["dates_heures"].add(date_heure)
        for nom, champ in (
            ("sm_rootzone", "sm_rootzone_m3_m3"),
            ("sm_surface", "sm_surface_m3_m3"),
        ):
            valeur = observation.get(champ)
            if valeur is not None:
                groupe[nom].append(_valider_valeur_humidite_smap(valeur, champ))

    resultats = []
    for jour, groupe in sorted(groupes.items()):
        debut_journee = datetime(
            jour.year, jour.month, jour.day, 1, 30, tzinfo=timezone.utc
        )
        dates_heures_attendues = {
            debut_journee + timedelta(hours=3 * index) for index in range(8)
        }
        couverture_horodatages_complete = (
            groupe["dates_heures"] == dates_heures_attendues
        )
        resultat = {
            "date": jour.isoformat(),
            "observations_3h_recues": len(groupe["dates_heures"]),
            "observations_3h_attendues": 8,
            "couverture_horodatages_complete": couverture_horodatages_complete,
            "latitude_cellule_deg": cellule_reference[0],
            "longitude_cellule_deg": cellule_reference[1],
        }
        for nom in ("sm_rootzone", "sm_surface"):
            valeurs = groupe[nom]
            moyenne_partielle = (
                round(sum(valeurs) / len(valeurs), 6) if valeurs else None
            )
            moyenne_complete = (
                moyenne_partielle
                if couverture_horodatages_complete and len(valeurs) == 8
                else None
            )
            resultat[f"{nom}_m3_m3_observations_valides"] = len(valeurs)
            resultat[f"{nom}_m3_m3_moyenne_partielle"] = moyenne_partielle
            resultat[f"{nom}_m3_m3_moyenne"] = moyenne_complete
        resultats.append(resultat)
    return resultats


def joindre_smap_pluie_par_jour(smap_journalier, pluie_journaliere):
    """Aligne les moyennes SMAP sur la pluie POWER par date, sans imputer les manquants."""
    if not isinstance(smap_journalier, (list, tuple)) or not smap_journalier:
        raise ValueError("smap_journalier doit être une liste non vide.")
    if not isinstance(pluie_journaliere, (list, tuple)) or not pluie_journaliere:
        raise ValueError("pluie_journaliere doit être une liste non vide.")

    pluies_par_date = {}
    for observation in pluie_journaliere:
        if not isinstance(observation, dict):
            raise TypeError("Chaque observation de pluie doit être un dictionnaire.")
        date_observation = observation.get("date")
        if not isinstance(date_observation, str):
            raise ValueError("Chaque observation de pluie doit avoir une date ISO.")
        try:
            jour = date.fromisoformat(date_observation)
        except ValueError as exc:
            raise ValueError(f"Date de pluie invalide : {date_observation!r}.") from exc
        if jour.isoformat() != date_observation:
            raise ValueError(f"Date de pluie invalide : {date_observation!r}.")
        if jour in pluies_par_date:
            raise ValueError(f"Date de pluie dupliquée : {date_observation}.")

        pluie = observation.get("pluie_mm")
        if pluie is not None:
            if isinstance(pluie, bool):
                raise TypeError("La pluie doit être une valeur numérique ou None.")
            try:
                pluie = float(pluie)
            except (TypeError, ValueError) as exc:
                raise ValueError("La pluie doit être une valeur numérique ou None.") from exc
            if not math.isfinite(pluie) or pluie < 0:
                raise ValueError("La pluie doit être finie et positive ou nulle.")
        pluies_par_date[jour] = pluie

    dates_smap_vues = set()
    resultats = []
    for observation in smap_journalier:
        if not isinstance(observation, dict):
            raise TypeError("Chaque observation journalière SMAP doit être un dictionnaire.")
        date_observation = observation.get("date")
        if not isinstance(date_observation, str):
            raise ValueError("Chaque observation journalière SMAP doit avoir une date ISO.")
        try:
            jour = date.fromisoformat(date_observation)
        except ValueError as exc:
            raise ValueError(f"Date SMAP invalide : {date_observation!r}.") from exc
        if jour.isoformat() != date_observation:
            raise ValueError(f"Date SMAP invalide : {date_observation!r}.")
        if jour in dates_smap_vues:
            raise ValueError(f"Date SMAP dupliquée : {date_observation}.")
        dates_smap_vues.add(jour)

        resultat = dict(observation)
        resultat["pluie_mm"] = pluies_par_date.get(jour)
        resultat["pluie_disponible"] = jour in pluies_par_date and pluies_par_date[jour] is not None
        resultats.append(resultat)
    return resultats


def coordonnees_vers_index(latitude, longitude, metadata):
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise ValueError("La latitude et la longitude doivent être des nombres finis.")

    distance_lat = metadata["lat_max"] - latitude
    distance_lon = longitude - metadata["lon_min"]

    row = math.floor(distance_lat / metadata["resolution"])
    col = math.floor(distance_lon / metadata["resolution"])

    if row < 0 or row >= metadata["max_rows"] or col < 0 or col >= metadata["max_cols"]:
        raise ValueError("Coordonnées en dehors des limites de la grille.")
    return row, col


def _valider_donnees_environnementales(donnees, metadata):
    """Valide pluie (mm/mois), température de surface (°C), humidité (fraction), NDVI."""
    valeurs = np.asarray(donnees, dtype=float)
    if valeurs.ndim == 3:
        format_valide = valeurs.shape[0] >= 1 and valeurs.shape[1:] == (12, 4)
    elif valeurs.ndim == 5:
        format_valide = (
            valeurs.shape[0] >= 1
            and valeurs.shape[1:3] == (metadata["max_rows"], metadata["max_cols"])
            and valeurs.shape[3:] == (12, 4)
        )
    else:
        format_valide = False

    if not format_valide:
        raise ValueError(
            "Les données doivent contenir 12 mois et avoir la forme (années, 12, 4) ou "
            "(années, lignes, colonnes, 12, 4)."
        )
    if not np.all(np.isfinite(valeurs)):
        raise ValueError("Les données environnementales contiennent des valeurs manquantes ou non finies.")
    if np.any(valeurs[..., 0] < 0):
        raise ValueError("La pluie doit être exprimée en mm/mois et ne peut pas être négative.")
    if np.any((valeurs[..., 1] < -90) | (valeurs[..., 1] > 70)):
        raise ValueError("La température doit être en °C et comprise entre -90 et 70.")
    if np.any((valeurs[..., 2] < 0) | (valeurs[..., 2] > 1)):
        raise ValueError("L'humidité du sol doit être une fraction comprise entre 0 et 1.")
    if np.any((valeurs[..., 3] < -1) | (valeurs[..., 3] > 1)):
        raise ValueError("Le NDVI doit être compris entre -1 et 1.")
    return valeurs


class EngineTerraCI:
    def __init__(self, metadata, donnees_environnementales=None, source_donnees=None):
        self.metadata = metadata
        if donnees_environnementales is None:
            if source_donnees is not None:
                raise ValueError("source_donnees ne peut être renseignée sans données importées.")
            aleatoire = np.random.default_rng(42)
            donnees_simulees = aleatoire.random((5, 12, 4))
            donnees_simulees[:, :, 0] *= 200
            donnees_simulees[:, :, 1] = 25 + donnees_simulees[:, :, 1] * 15
            donnees_simulees[:, :, 2] *= 0.4
            donnees_simulees[:, :, 3] *= 0.9
            self.E = donnees_simulees
            self.donnees_simulees = True
            self.source_donnees = "simulation reproductible"
        else:
            self.E = _valider_donnees_environnementales(donnees_environnementales, metadata)
            self.donnees_simulees = False
            if source_donnees is not None and (
                not isinstance(source_donnees, str) or not source_donnees.strip()
            ):
                raise ValueError("source_donnees doit être un nom de source non vide.")
            self.source_donnees = source_donnees or "tableau fourni; source à documenter"

    def executer(self, lat, lon, local_data, priorites=None):
        """Compare des scénarios à partir de données normalisées (pluie, température, humidité, NDVI).

        Données globales : (années, 12 mois, 4 variables).
        Données géolocalisées : (années, lignes, colonnes, 12 mois, 4 variables).
        """
        if not isinstance(local_data, dict):
            raise TypeError("local_data doit être un dictionnaire.")
        if priorites is None:
            priorites = []
        if not isinstance(priorites, (list, tuple)) or not all(
            isinstance(nom, str) for nom in priorites
        ):
            raise TypeError("priorites doit être une liste ou un tuple de noms de stratégies.")
        if len(set(priorites)) != len(priorites):
            raise ValueError("priorites ne doit pas contenir de doublons.")
        strategies_inconnues = set(priorites) - MATRICE_POIDS.keys()
        if strategies_inconnues:
            raise ValueError(
                f"Stratégie(s) inconnue(s) dans priorites : {', '.join(sorted(strategies_inconnues))}."
            )
        ordre_strategies = list(priorites) + [
            nom for nom in MATRICE_POIDS if nom not in priorites
        ]

        row = col = None
        if self.E.ndim == 5:
            row, col = coordonnees_vers_index(lat, lon, self.metadata)
            donnees_cellule = self.E[:, row, col, :, :]
        else:
            if (
                not math.isfinite(lat)
                or not math.isfinite(lon)
                or not -90 <= lat <= 90
                or not -180 <= lon <= 180
            ):
                raise ValueError("La latitude et la longitude doivent être des coordonnées valides.")
            donnees_cellule = self.E
        M = np.mean(donnees_cellule, axis=0)

        saison_definie = "mois_saison" in local_data
        mois_saison = local_data.get("mois_saison", list(range(1, 13)))
        if (
            not isinstance(mois_saison, (list, tuple))
            or not mois_saison
            or any(type(mois) is not int or mois < 1 or mois > 12 for mois in mois_saison)
            or len(set(mois_saison)) != len(mois_saison)
        ):
            raise ValueError("mois_saison doit contenir des numéros uniques de 1 à 12.")
        indices_mois = [mois - 1 for mois in mois_saison]

        pluie_mensuelle_locale = local_data.get("pluie_mensuelle_mm")
        if pluie_mensuelle_locale is not None:
            pluie_locale = np.asarray(pluie_mensuelle_locale, dtype=float)
            if pluie_locale.shape != (12,) or not np.all(np.isfinite(pluie_locale)) or np.any(pluie_locale < 0):
                raise ValueError("pluie_mensuelle_mm doit contenir 12 valeurs finies positives ou nulles.")
            M[:, 0] = pluie_locale
        elif "pluie_janvier" in local_data:
            pluie_janvier_locale = float(local_data["pluie_janvier"])
            if not math.isfinite(pluie_janvier_locale) or pluie_janvier_locale < 0:
                raise ValueError("pluie_janvier doit être une valeur finie positive ou nulle.")
            M[0, 0] = pluie_janvier_locale

        pluie_periode_estimee = float(np.sum(M[indices_mois, 0]))
        temp_periode_max_moyenne = float(np.max(M[indices_mois, 1]))
        humidite_periode = float(np.mean(M[indices_mois, 2]))
        ndvi_periode = float(np.mean(M[indices_mois, 3]))

        # MODULE 2 : indicateurs de contexte; aucun pourcentage de fiabilité n'est inventé.
        failles = {}
        if ndvi_periode < 0.35:
            failles["sol_nu"] = True
            if temp_periode_max_moyenne > 34.0:
                failles["alerte"] = "DESSECHEMENT_CRITIQUE"

        # MODULE 3 : filtres climatiques et de succession, à valider localement.
        culture_eligibles = []
        culture_precedente = local_data.get("culture_actuelle")
        culture_maraichere_non_scoree = False
        if culture_precedente is not None:
            if not isinstance(culture_precedente, str):
                raise TypeError("culture_actuelle doit être un nom de culture textuel.")
            culture_normalisee = _normaliser_nom_culture(culture_precedente)
            if culture_normalisee in CATALOGUE_CULTURES:
                culture_precedente = culture_normalisee
                famille_precedente = CATALOGUE_CULTURES[culture_precedente]["famille"]
            elif culture_normalisee in CULTURES_MARAICHERES_RECONNUES:
                culture_precedente = CULTURES_MARAICHERES_RECONNUES[culture_normalisee]
                famille_precedente = None
                culture_maraichere_non_scoree = True
            else:
                raise ValueError(
                    f"Culture précédente inconnue : {culture_precedente!r}. "
                    "Cultures scorées : "
                    f"{', '.join(CATALOGUE_CULTURES)}. "
                    "Les cultures maraîchères reconnues sont disponibles sans score."
                )
        else:
            famille_precedente = None

        for nom, specs in CATALOGUE_CULTURES.items():
            if culture_maraichere_non_scoree:
                continue
            # Ce seuil expérimental n'est pas un seuil biologique validé.
            if temp_periode_max_moyenne > specs["temp_surface_max_c"]:
                continue  # Culture non éligible
            # Heuristique simplifiée : une famille différente est privilégiée.
            if famille_precedente is not None and specs['famille'] == famille_precedente:
                continue  # Évite la monoculture
            culture_eligibles.append(nom)

        # MODULE 4 : notation multicritère pondérée (pas une méthode AHP).
        strategies_scores = {}
        noms_criteres = ("eau", "azote", "protection_sol", "marche")
        noms_criteres_affiches = {
            "eau": "disponibilité en eau",
            "azote": "contribution à l'azote",
            "protection_sol": "couverture et protection du sol",
            "marche": "valeur de marché indicative",
        }
        descriptions_strategies = {
            "temoin": "Scénario témoin à pondération économique; il ne représente pas nécessairement la rotation actuelle.",
            "hydrique": "Scénario qui donne davantage de poids au critère eau.",
            "regeneration": "Scénario qui donne davantage de poids à l'azote et à la protection du sol.",
        }
        for nom_strat in ordre_strategies:
            poids = MATRICE_POIDS[nom_strat]
            meilleur_score = None
            meilleure_culture = None
            meilleurs_indicateurs = None
            meilleures_contributions = None

            for cult in culture_eligibles:
                specs = CATALOGUE_CULTURES[cult]

                # Scores ramenés entre 0 et 1; le déficit de pluie dépend du lieu et de la saison.
                I_eau = float(np.clip(
                    pluie_periode_estimee / specs["pluie_min_saison_mm"], 0.0, 1.0
                ))
                I_azote = float(np.clip(
                    (specs["gain_azote"] + 0.3) / 1.2, 0.0, 1.0
                ))
                I_erosion = float(np.clip(specs["couverture_sol"], 0.0, 1.0))
                I_marche = float(np.clip(specs["valeur_marche_xof"] / 1000.0, 0.0, 1.0))

                vecteur_indices = np.array([I_eau, I_azote, I_erosion, I_marche])
                contributions = vecteur_indices * poids * 100

                # Produit scalaire pour obtenir le score final
                score = float(np.sum(contributions))
                if meilleur_score is None or score > meilleur_score:
                    meilleur_score = score
                    meilleure_culture = cult
                    meilleurs_indicateurs = dict(zip(noms_criteres, vecteur_indices.tolist()))
                    meilleures_contributions = dict(zip(noms_criteres, contributions.tolist()))

            if (
                meilleure_culture is None
                or meilleur_score is None
                or meilleurs_indicateurs is None
                or meilleures_contributions is None
            ):
                strategies_scores[nom_strat] = {
                    "culture": None,
                    "score": None,
                    "explication": {
                        "scenario": descriptions_strategies[nom_strat],
                        "pourquoi": (
                            "La culture maraîchère est reconnue, mais le catalogue ne contient pas "
                            "de paramètres validés pour calculer une recommandation."
                            if culture_maraichere_non_scoree
                            else "Aucune culture n'a passé les filtres climatiques et de rotation."
                        ),
                        "benefices_potentiels": [],
                        "indicateurs_et_contributions": {},
                        "donnees_utilisees": {},
                        "informations_manquantes": (
                            [
                                "Paramètres locaux validés pour les cultures maraîchères.",
                                "Données de rendement, coûts et calendrier correspondant à la parcelle.",
                            ]
                            if culture_maraichere_non_scoree
                            else [
                                "Données environnementales réelles et période exacte de la saison culturale.",
                                "Culture précédente à renseigner pour appliquer le filtre de rotation.",
                            ]
                        ),
                        "risques_a_valider_localement": [
                            "Les seuils du catalogue doivent être confirmés par des spécialistes locaux.",
                        ],
                    },
                }
                continue

            specs_recommandees = CATALOGUE_CULTURES[meilleure_culture]
            critere_dominant = noms_criteres[int(np.argmax(poids))]
            benefices = []
            if specs_recommandees["gain_azote"] > 0:
                benefices.append("Potentiel de contribution à l'azote indiqué par le catalogue, à valider localement.")
            if specs_recommandees["couverture_sol"] >= 0.6:
                benefices.append("Couverture du sol indiquée par le catalogue, pouvant limiter son exposition.")
            if specs_recommandees["pluie_min_saison_mm"] < 400:
                benefices.append("Seuil minimal de pluie du catalogue inférieur à 400 mm par saison.")
            if not benefices:
                benefices.append("Aucun bénéfice spécifique n'est déduit des critères simplifiés du prototype.")

            strategies_scores[nom_strat] = {
                "culture": meilleure_culture,
                "score": round(meilleur_score, 1),
                "explication": {
                    "scenario": descriptions_strategies[nom_strat],
                    "pourquoi": (
                        f"{meilleure_culture} obtient le meilleur score parmi les cultures admissibles. "
                        f"Le critère le plus pondéré est : {noms_criteres_affiches[critere_dominant]}."
                    ),
                    "benefices_potentiels": benefices,
                    "indicateurs_et_contributions": {
                        nom: {
                            "indicateur": round(meilleurs_indicateurs[nom], 2),
                            "contribution_au_score": round(meilleures_contributions[nom], 1),
                        }
                        for nom in noms_criteres
                    },
                    "indicateurs_contextuels_non_notes": {
                        "humidite_moyenne_sol_fraction": round(humidite_periode, 3),
                        "ndvi_moyen": round(ndvi_periode, 3),
                        "note": (
                            "L'humidité du sol et le NDVI décrivent le contexte; ils ne modifient pas "
                            "le score de culture tant que leurs références agronomiques ne sont pas calibrées."
                        ),
                    },
                    "donnees_utilisees": {
                        "mois_analyses": mois_saison,
                        "temperature_mensuelle_moyenne_max_c": round(temp_periode_max_moyenne, 1),
                        "pluie_cumulee_sur_periode_mm": round(pluie_periode_estimee, 1),
                        "humidite_moyenne_sol_fraction": round(humidite_periode, 3),
                        "ndvi_moyen": round(ndvi_periode, 3),
                        "origine_donnees": self.source_donnees,
                        "grille_spatiale_utilisee": self.E.ndim == 5,
                        "culture_precedente": culture_precedente,
                        "famille_culturale": specs_recommandees["famille"],
                        "gain_azote_catalogue": specs_recommandees["gain_azote"],
                        "couverture_sol_catalogue": specs_recommandees["couverture_sol"],
                        "valeur_marche_catalogue_xof": specs_recommandees["valeur_marche_xof"],
                    },
                    "informations_manquantes": [
                        "Période de culture locale précise."
                        if not saison_definie
                        else "La saison renseignée doit être confirmée avec des données et pratiques locales.",
                        "Sans mois_saison, le cumul annuel est comparé à un seuil saisonnier; le score d'eau est alors seulement exploratoire."
                        if not saison_definie
                        else "Les mois indiqués sont traités comme la saison; vérifier les cumuls de pluie et le calendrier local.",
                        "Source, date, résolution et incertitude des données importées."
                        if not self.donnees_simulees
                        else "Observations satellitaires et mesures agricoles réelles; la simulation ne sert qu'à la démonstration.",
                        "Analyses locales du sol (pH, matière organique, nutriments) et pratiques de l'exploitation.",
                        "Prix et débouchés locaux vérifiés; la valeur du catalogue est indicative.",
                    ],
                    "risques_a_valider_localement": [
                        "Confirmer l'adaptation variétale et les seuils climatiques avec un agronome local.",
                        "Vérifier les contraintes de ravageurs, de main-d'œuvre, d'intrants et de marché.",
                    ],
                },
            }
        # MOTEUR DE VULGARISATION TEXTUELLE
        texte_diagnostic = ""
        if culture_maraichere_non_scoree:
            texte_diagnostic = (
                f"La culture maraîchère « {culture_precedente} » est reconnue, mais TerraCI "
                "ne dispose pas encore de paramètres agronomiques validés pour calculer une "
                "recommandation. Aucun score n'est produit."
            )
        elif not culture_eligibles:
            texte_diagnostic = (
                "Aucune culture du catalogue ne respecte actuellement les critères climatiques "
                "et de rotation. Vérifiez les données et la culture précédente."
            )
        elif failles.get("alerte") == "DESSECHEMENT_CRITIQUE":
            culture_recommandee = strategies_scores["regeneration"]["culture"]
            specs_recommandees = CATALOGUE_CULTURES[culture_recommandee]
            origine_donnees = "simulées" if self.donnees_simulees else "fournies au moteur"
            texte_diagnostic = (
                f"Alerte de stress potentiel : le NDVI moyen sur la période est faible "
                f"({ndvi_periode:.2f}) et la température mensuelle moyenne maximale est "
                f"{temp_periode_max_moyenne:.1f}°C. Les données sont {origine_donnees}; "
                "cette alerte doit être vérifiée sur le terrain. "
                f"La stratégie 'Régénération' recommande de planter {culture_recommandee} "
                f"avec un score indicatif de {strategies_scores['regeneration']['score']}. "
                f"Le catalogue lui attribue une couverture du sol de "
                f"{specs_recommandees['couverture_sol']:.0%}; faites valider cette piste localement."
            )

        if culture_maraichere_non_scoree:
            statut_rotation = "reconnue_non_scoree"
            note_rotation = (
                "Culture maraîchère reconnue à partir des données locales, mais non scorée "
                "faute de paramètres agronomiques validés."
            )
        elif culture_precedente is not None:
            statut_rotation = "renseignee"
            note_rotation = (
                "Culture précédente fournie par l'utilisateur; ce n'est pas encore une séquence "
                "de rotation pluriannuelle."
            )
        else:
            statut_rotation = "non_renseignee"
            note_rotation = "Renseignez culture_actuelle pour comparer avec les pratiques de l'exploitation."

        rotation_actuelle = {
            "culture": culture_precedente,
            "statut": statut_rotation,
            "note": note_rotation,
        }
        avertissements = [
            "Les scores sont des indicateurs de comparaison, pas des probabilités de rendement ni des conseils agronomiques validés.",
            "Les seuils de pluie et de température ainsi que les scores d'azote, de couverture et de marché du catalogue sont des hypothèses non validées localement.",
            "Le seuil thermique est comparé à la température mensuelle moyenne maximale de la période, pas à un pic journalier.",
            "L'humidité du sol et le NDVI sont des indicateurs contextuels; ils ne sont pas inclus dans le score multicritère.",
        ]
        if culture_maraichere_non_scoree:
            avertissements.append(
                "La culture maraîchère est reconnue, mais aucune recommandation chiffrée n'est calculée sans paramètres validés."
            )
        if self.donnees_simulees:
            avertissements.append("Les données environnementales sont simulées et identiques pour toutes les coordonnées.")
        elif self.E.ndim == 3:
            avertissements.append("Les données importées ne sont pas géolocalisées; toutes les coordonnées reçoivent le même climat.")
        if not saison_definie:
            avertissements.append(
                "Aucun mois de saison n'a été fourni : le cumul annuel est comparé à des seuils saisonniers."
            )

        contexte_empirique = (
            [dict(fait) for fait in CONTEXTE_EMPIRIQUE_BOUAKE]
            if isinstance(self.metadata.get("zone"), str)
            and _normaliser_nom_culture(self.metadata["zone"]) == "bouake"
            else []
        )

        return {
            'statut': (
                'catalogue_incomplet'
                if culture_maraichere_non_scoree
                else 'success' if culture_eligibles else 'aucune_culture_eligible'
            ),
            'contexte_empirique_bouake': contexte_empirique,
            'coordonnees_matrice': {'ligne':row, 'colonne': col},
            'rotation_actuelle': rotation_actuelle,
            'qualite_donnees': {
                "origine": self.source_donnees,
                "nombre_annees": int(donnees_cellule.shape[0]),
                "grille_spatiale": self.E.ndim == 5,
                "saison_specifiee": saison_definie,
            },
            'avertissements': avertissements,
            'diagnostic_vulgarise': texte_diagnostic,
            'strategies_classement': strategies_scores

        }
    
