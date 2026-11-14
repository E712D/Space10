from datetime import date, timedelta

def season_window(label: str) -> tuple[date, date]:
    """
    Retourne la date de début et de fin d'une saison.
    Format attendu : 'YYYY-A' (01 mars -> 31 juil) ou 'YYYY-B' (01 sept -> 30 nov).
    """
    try:
        year_str, period = label.split('-')
        year = int(year_str)
    except (ValueError, AttributeError):
        raise ValueError(f"Format de saison invalide : {label}. Utilisez YYYY-A ou YYYY-B.")

    if period == 'A':
        return date(year, 3, 1), date(year, 7, 31)
    elif period == 'B':
        return date(year, 9, 1), date(year, 11, 30)
    else:
        raise ValueError(f"Période de saison inconnue : {period}. Attendu 'A' ou 'B'.")

def next_season(today: date) -> str:
    """
    Détermine la première saison dont la date de début est strictement supérieure à today.
    """
    year = today.year
    for y in [year, year + 1]:
        for period in ['A', 'B']:
            label = f"{y}-{period}"
            start_date, _ = season_window(label)
            if start_date > today:
                return label
    return f"{year + 1}-A"

def current_season(today: date) -> str | None:
    """
    Retourne le libellé de la saison contenant today, ou None si entre deux saisons.
    """
    year = today.year
    for y in [year - 1, year, year + 1]:
        for period in ['A', 'B']:
            label = f"{y}-{period}"
            start_date, end_date = season_window(label)
            if start_date <= today <= end_date:
                return label
    return None

def following_season(label: str) -> str:
    """
    Passe à la saison suivante : A -> B de la même année, B -> A de l'année suivante.
    """
    try:
        year_str, period = label.split('-')
        year = int(year_str)
    except (ValueError, AttributeError):
        raise ValueError(f"Format de saison invalide : {label}")

    if period == 'A':
        return f"{year}-B"
    else:
        return f"{year + 1}-A"

def default_lock_date(start: date) -> date:
    """
    Date de verrouillage par défaut : 14 jours avant le début de la saison.
    """
    return start - timedelta(days=14)

def season_months(start: date, end: date) -> list[tuple[int, date, date]]:
    """
    Découpe une saison en une liste de tuples (period_index, début_mois, fin_mois).
    """
    months = []
    current_start = start
    index = 0
    
    while current_start <= end:
        if current_start.month == 12:
            next_month = date(current_start.year + 1, 1, 1)
        else:
            next_month = date(current_start.year, current_start.month + 1, 1)
            
        current_end = min(next_month - timedelta(days=1), end)
        months.append((index, current_start, current_end))
        
        current_start = next_month
        index += 1
        
    return months

def season_length_days(label: str) -> int:
    """
    Retourne la durée totale en jours d'une saison.
    """
    start, end = season_window(label)
    return (end - start).days + 1