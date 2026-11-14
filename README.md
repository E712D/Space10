# S3A — NASA Space Apps Challenge Abidjan 2026

Prédiction de la saison agricole à partir de données NASA, recommandation de cultures, bilan verrouillable et assistant vocal.

## Équipe
| Rôle | Intervenant |
|---|---|
| Dev1 · ML | Yann |
| Dev2 · Données Django | Bamba Prince |
| Dev3 · Frontend | Yapi Ochou |
| Dev4 · Backend Django et IA | Fulbert |
| Dev5 · QA / Infra | Diomande |

## Structure
- `ml/` : modèle et ingestion NASA POWER
- `backend/` : Django, DRF, moteur agronomique
- `frontend/` : React + TypeScript
- `contracts/` : schémas JSON, exemples, `openapi.json` (source de vérité)
- `tests/` : contrats, intégration, e2e
- `docs/` : architecture, `status.md`

## Démarrage
```bash
git clone <url-du-depot>
cd s3a
cp .env.example .env
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements/constraints.txt
make up
```

## Commandes
`make up` · `make down` · `make db-reset` · `make seed` · `make test` · `make test-integration` · `make lint` · `make e2e` · `make export-openapi`

## Règles
- Identifiants de code en anglais `snake_case`, textes affichés en français.
- Aucun changement de contrat sans PR approuvée.
- Jamais de `.env` ni de secret dans git.
- Branches : `develop` pour le travail, `main` protégée.