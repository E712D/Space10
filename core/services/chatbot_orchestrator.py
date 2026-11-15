import hashlib
import logging
import re
from urllib.parse import quote

import httpx
from django.core.cache import cache
from django.utils import timezone

from persistence.repositories import (
    CropRepository,
    PlotRepository,
    ReportRepository,
    SeasonRepository,
    WeatherRepository,
)
from core.services.ml_adapter import MlAdapter
from core.services.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

CROP_CLIMATE_PROFILES = {
    "tomate": {
        "aliases": ("tomate", "tomates"),
        "article": "la",
        "temperature": "18 à 27 °C",
        "heat_limit": "au-delà de 35 °C, la nouaison et le rendement peuvent diminuer",
        "water": "400 à 600 mm par cycle, avec un apport régulier sans stagnation",
        "soil": "sol profond, fertile et bien drainé, pH indicatif de 6,0 à 6,8",
        "season": "la période la moins pluvieuse, généralement de novembre à février en Côte d'Ivoire",
        "season_note": "La tomate supporte mal les pluies persistantes : prévoyez une irrigation maîtrisée et un bon drainage.",
    },
    "piment": {
        "aliases": ("piment", "piments", "poivron"),
        "article": "le",
        "temperature": "20 à 30 °C",
        "heat_limit": "au-delà de 35 °C, la floraison et la nouaison peuvent être perturbées",
        "water": "500 à 800 mm par cycle, avec une humidité régulière sans engorgement",
        "soil": "sol fertile, léger et bien drainé, pH indicatif de 5,5 à 6,8",
        "season": "la période moins pluvieuse, en adaptant la date à l'irrigation et au risque local de pluie",
        "season_note": "Évitez les pluies continues pendant la floraison et assurez un drainage efficace.",
    },
}


class ChatbotOrchestrator:
    """Selects trusted data tools and turns their results into a concise answer."""

    cache_ttl = 600
    web_headers = {"User-Agent": "Mozilla/5.0 (compatible; Space10/1.0; +https://example.com)", "Accept": "application/json"}

    def __init__(self, plot, question):
        self.plot = plot
        self.question = question.strip()

    def answer(self):
        cache_key = self._cache_key()
        cached = cache.get(cache_key)
        if cached:
            return {**cached, "cached": True}

        intent = self._classify()
        try:
            if intent == "out_of_scope":
                result = {
                    "answer_text": "Je suis spécialisé dans l'agriculture, les parcelles, les cultures et la météo agricole. Posez-moi une question dans ce domaine.",
                    "sources": [],
                }
            elif intent == "general_knowledge":
                result = self._wiki_fallback()
            else:
                analysis = self._run_analysis()
                result = self._answer_from_analysis(intent, analysis)
        except (httpx.HTTPError, ValueError, RuntimeError) as exc:
            logger.warning("Chatbot tool failed for plot %s: %s", self.plot.pk, exc)
            result = {
                "answer_text": "Je ne peux pas vérifier cette information pour le moment. Réessayez dans quelques instants.",
                "sources": [],
                "data_missing": True,
            }

        response = {
            "intent": intent,
            "answer_text": result["answer_text"],
            "speak_text": result["answer_text"],
            "data_missing": result.get("data_missing", False),
            "llm_used": False,
            "sources": result.get("sources", []),
            "cached": False,
        }
        cache.set(cache_key, response, self.cache_ttl)
        return response

    def _classify(self):
        normalized = self.question.casefold()
        if any(word in normalized for word in (
            "football", "sport", "match", "ligue", "championnat", "film", "série",
            "musique", "politique", "élection", "crypto", "recette",
        )):
            return "out_of_scope"
        if any(phrase in normalized for phrase in ("faire attention", "à surveiller", "a surveiller", "période critique", "periode critique")):
            return "critical_periods"
        if not self._is_agricultural(normalized):
            return "out_of_scope"
        if self._crop_name(normalized) and any(word in normalized for word in (
            "saison", "période", "quand", "moment", "planter", "semer",
        )):
            return "crop_season"
        if (self._crop_name(normalized) or "culture de " in normalized) and any(word in normalized for word in (
            "climat", "adapté", "besoin", "condition", "température", "sol",
        )):
            return "crop_knowledge"
        if any(word in normalized for word in ("pluie", "pleuvoir", "précipitation", "météo")):
            return "rain_forecast"
        if any(word in normalized for word in ("température", "chaleur", "chaud", "canicule")):
            return "heat_forecast"
        if any(word in normalized for word in ("humidité", "sécheresse", "eau", "irrigation")):
            return "water_status"
        if any(word in normalized for word in ("planter", "culture", "semer", "cultiver")):
            return "recommend_crop"
        if any(word in normalized for word in ("attention", "risque", "danger", "critique")):
            return "critical_periods"
        if any(word in normalized for word in ("saison", "calendrier agricole", "période de semis", "quand semer")):
            return "season_calendar"
        if any(word in normalized for word in ("quoi", "définition", "signifie", "comment fonctionne", "qu'est-ce", "qu est-ce", "expliquer")):
            return "general_knowledge"
        if any(word in normalized for word in ("mon champ", "ma parcelle", "mon sol", "ma culture", "ma récolte")):
            return "plot_summary"
        return "general_knowledge"

    @staticmethod
    def _is_agricultural(question):
        terms = (
            "agric", "champ", "parcelle", "culture", "récolte", "sem", "plant",
            "sol", "terre", "engrais", "irrig", "eau", "pluie", "météo",
            "climat", "saison", "peste", "maladie", "ravageur", "maïs", "mais",
            "riz", "manioc", "igname", "sorgho", "arachide", "niébé", "soja",
            "cacao", "café", "banane", "rendement", "fertilis", "humidité",
            "sécheresse", "température", "récolte", "bétail", "élevage",
        )
        return any(term in question for term in terms)

    @staticmethod
    def _crop_name(question):
        for name, profile in CROP_CLIMATE_PROFILES.items():
            if any(alias in question for alias in profile["aliases"]):
                return name
        return None

    def _run_analysis(self):
        repositories = type("Repositories", (), {
            "plots": PlotRepository(),
            "seasons": SeasonRepository(),
            "weather": WeatherRepository(),
            "crops": CropRepository(),
            "reports": ReportRepository(),
        })()
        return Orchestrator(repositories, MlAdapter()).run_analysis(
            plot_id=self.plot.pk,
            season_label=None,
            today=timezone.now().date(),
        )

    def _answer_from_analysis(self, intent, result):
        prediction = result.get("prediction") or {}
        summary = prediction.get("season_summary", {})
        features = summary.get("features", {})
        periods = prediction.get("periods") or []
        sources = [{"name": "Analyse agronomique Space10", "type": "model"}]
        recommendations = result.get("recommendations") or []

        crops = []
        for item in recommendations[:3]:
            rotation = item.get("rotation") or [{}]
            code = rotation[0].get("crop_code")
            if code:
                crops.append(code.replace("_", " ").capitalize())

        if intent == "rain_forecast":
            total = (summary.get("precip_total_mm") or {}).get("value")
            wettest = max(periods, key=lambda p: (p.get("features", {}).get("precip_mm", {}).get("value") or 0), default=None)
            if total is None:
                return {"answer_text": "Les précipitations prévues ne sont pas disponibles.", "sources": sources, "data_missing": True}
            detail = f" Le mois le plus arrosé est {wettest['period']}." if wettest else ""
            return {"answer_text": f"Pour votre parcelle, environ {round(total)} mm sont prévus sur la saison.{detail}", "sources": sources}

        if intent == "heat_forecast":
            hottest = max(periods, key=lambda p: (p.get("features", {}).get("t2m_max_c", {}).get("value") or 0), default=None)
            if not hottest:
                return {"answer_text": "Les températures prévues ne sont pas disponibles.", "sources": sources, "data_missing": True}
            values = hottest["features"]
            return {
                "answer_text": f"Le pic est estimé à {values['t2m_max_c']['value']} °C en {hottest['period']}, avec environ {values['heat_stress_days']['value']} jours de stress thermique.",
                "sources": sources,
            }

        if intent == "water_status":
            stress = (features.get("water_stress_index") or {}).get("value")
            moisture = (features.get("sm_root") or {}).get("value")
            if stress is None and moisture is None:
                return {"answer_text": "Les indicateurs d'humidité du sol ne sont pas disponibles.", "sources": sources, "data_missing": True}
            return {
                "answer_text": f"L'humidité racinaire est estimée à {round((moisture or 0) * 100)} %, avec un stress hydrique de {round((stress or 0) * 100)} %. Surveillez l'irrigation si nécessaire.",
                "sources": sources,
            }

        if intent == "crop_knowledge":
            crop_name = self._crop_name(self.question.casefold())
            profile = CROP_CLIMATE_PROFILES.get(crop_name)
            if not profile:
                return self._wiki_fallback()
            local = max(
                periods,
                key=lambda item: (item.get("features", {}).get("t2m_max_c", {}).get("value") or 0),
                default=None,
            )
            local_detail = ""
            if local:
                local_max = local["features"]["t2m_max_c"]["value"]
                local_detail = (
                    f" Pour votre parcelle, le maximum prévu atteint {local_max} °C en {local['period']} ; "
                    "il faut donc vérifier le risque de chaleur avant de retenir cette culture."
                )
            return {
                "answer_text": (
                    f"Pour {profile['article']} {crop_name}, le climat le plus favorable se situe autour de {profile['temperature']}. "
                    f"{profile['heat_limit']}. Besoin en eau : {profile['water']}. "
                    f"Le sol conseillé est un {profile['soil']}.{local_detail}"
                ),
                "sources": [
                    {"name": f"Référentiel agronomique {crop_name}", "type": "model"},
                    *sources,
                ],
            }

        if intent == "crop_season":
            crop_name = self._crop_name(self.question.casefold())
            profile = CROP_CLIMATE_PROFILES.get(crop_name)
            if not profile:
                return {"answer_text": "La saison de cette culture n'est pas encore référencée.", "sources": sources, "data_missing": True}
            return {
                "answer_text": (
                    f"Pour {profile['article']} {crop_name}, la meilleure période est {profile['season']}. "
                    f"{profile['season_note']} Cette recommandation doit être ajustée selon les pluies et "
                    "l'irrigation réellement disponibles sur votre parcelle."
                ),
                "sources": [
                    {"name": f"Référentiel agronomique {crop_name}", "type": "model"},
                    *sources,
                ],
            }

        if intent == "recommend_crop":
            if not crops:
                return {"answer_text": "Aucune culture n'est suffisamment fiable avec les données actuelles.", "sources": sources, "data_missing": True}
            total_rain = (summary.get("precip_total_mm") or {}).get("value")
            water_stress = (features.get("water_stress_index") or {}).get("value")
            context = []
            if total_rain is not None:
                context.append(f"{round(total_rain)} mm de pluie prévus")
            if water_stress is not None:
                context.append(f"{round(water_stress * 100)} % de stress hydrique")
            context_text = f" selon l'analyse locale ({', '.join(context)})" if context else ""
            return {
                "answer_text": (
                    f"Pour votre parcelle{context_text}, la culture la mieux adaptée est {crops[0]}. "
                    f"Alternatives : {', '.join(crops[1:]) or 'aucune'}."
                ),
                "sources": sources,
            }

        if intent == "critical_periods":
            critical = [item.get("message_fr") for item in prediction.get("critical_periods", []) if item.get("message_fr")]
            if not critical:
                for period in periods:
                    features = period.get("features", {})
                    period_name = period.get("period", "la période concernée")
                    heat_days = (features.get("heat_stress_days") or {}).get("value") or 0
                    rain = (features.get("precip_mm") or {}).get("value") or 0
                    if heat_days > 0:
                        critical.append(f"{period_name} : environ {round(heat_days)} jours de stress thermique.")
                    elif rain >= 300:
                        critical.append(f"{period_name} : pluies importantes prévues ({round(rain)} mm).")
            return {
                "answer_text": "Périodes à surveiller : " + " ".join(critical[:3]) if critical else "Aucune période critique n'est signalée.",
                "sources": sources,
            }

        if intent == "season_calendar":
            season = result.get("season") or {}
            season_label = prediction.get("season_label") or prediction.get("season", {}).get("label") or season.get("label")
            season_start = prediction.get("season_start") or season.get("start_date")
            season_end = prediction.get("season_end") or season.get("end_date")
            if season_label and season_start and season_end:
                phase = "grande saison agricole" if season_label.endswith("-A") else "petite saison agricole"
                return {
                    "answer_text": (
                        f"Pour la Côte d'Ivoire, la {phase} prévue pour votre parcelle est "
                        f"{season_label}, du {season_start} au {season_end}. "
                        f"Les prévisions sont découpées par mois pour guider les semis et le suivi."
                    ),
                    "sources": sources,
                }
            return {
                "answer_text": "Le calendrier de la prochaine saison agricole n'est pas disponible pour cette parcelle.",
                "sources": sources,
                "data_missing": True,
            }

        return {
            "answer_text": f"Pour votre parcelle, la recommandation principale est {crops[0] if crops else 'indisponible'}. Vous pouvez demander la pluie, la chaleur, l'eau ou les risques.",
            "sources": sources,
        }

    def _wiki_fallback(self):
        terms = [
            word for word in re.findall(r"[a-zàâçéèêëîïôûùüÿœ-]+", self.question.casefold())
            if len(word) > 3 and word not in {"quoi", "comment", "fonctionne", "qu'est"}
        ]
        if not terms:
            return {"answer_text": "Je n'ai pas trouvé le sujet à rechercher.", "sources": [], "data_missing": True}
        response = httpx.get(
            "https://fr.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": " ".join(terms), "srlimit": 1, "format": "json"},
            headers=self.web_headers,
            timeout=8,
        )
        response.raise_for_status()
        pages = response.json().get("query", {}).get("search", [])
        if not pages:
            return {"answer_text": "Je n'ai trouvé aucune source fiable pour cette question.", "sources": [], "data_missing": True}
        title = pages[0]["title"]
        summary = httpx.get(
            f"https://fr.wikipedia.org/api/rest_v1/page/summary/{quote(title)}",
            headers=self.web_headers,
            timeout=8,
        )
        summary.raise_for_status()
        extract = summary.json().get("extract")
        if not extract:
            return {"answer_text": "La source trouvée ne contient pas de réponse exploitable.", "sources": [], "data_missing": True}
        return {
            "answer_text": extract,
            "sources": [{"name": f"Wikipédia : {title}", "type": "web", "url": f"https://fr.wikipedia.org/wiki/{quote(title)}"}],
        }

    def _cache_key(self):
        digest = hashlib.sha256(f"{self.plot.pk}:{self.question.casefold()}".encode()).hexdigest()
        return f"chatbot:v6:{digest}"
