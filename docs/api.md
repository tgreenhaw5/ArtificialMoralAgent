# REST API (v1)

Interactive docs: `/docs` (OpenAPI). Authenticate with an API key (`ama keys create <label>`, or
`POST /api/v1/keys` while signed in), sent as `Authorization: Bearer ama_…`. Every evaluation response
includes `general_disclaimer`. If the safety triage flags a crisis, the response is `{"is_crisis": true,
"hotlines": [...]}` instead of an analysis.

| Method + path | Does | Auth |
|---|---|---|
| `POST /api/v1/evaluations` `{dilemma, model?}` | Full evaluation. `?stream=true` sends server-sent events: `triage`, 4 × `framework`, `arbiter`, `done` | key / signed in (guests: demo rules) |
| `GET /api/v1/evaluations/{id}` | One evaluation | public if published |
| `POST /api/v1/evaluations/{id}/frameworks/{name}` | Re-run one framework, optionally with another `model` | key |
| `POST /api/v1/quick-check` `{action, context}` | Fast first view: proceed yes/no/with_care, concerns | key |
| `POST /api/v1/triage` `{text}` | Safety triage only | key |
| `GET /api/v1/search?q=` | Similar published dilemmas | public (rate-limited) |
| `GET /api/v1/dilemmas` | Knowledge base, newest first | public while `AMA_KB_PUBLIC_UNTIL` allows |
| `POST /api/v1/feedback/{id}` `{rating: 1 or -1}` | Helpful / not helpful | public (rate-limited) |
| `GET /api/v1/frameworks` · `GET /api/v1/config` · `GET /api/v1/health` | Info | public |
| `GET/POST /api/v1/submissions…` · `POST /api/v1/dilemmas/{id}/publish` | Review queue, publishing | signed in |
| `DELETE /api/v1/submissions/{id}` (or `/api/v1/dilemmas/{id}`) | Delete a dilemma permanently | signed in |
| `GET/POST/DELETE /api/v1/keys` | API keys | signed in |

The fields of an evaluation are a stable contract within v1:
- `verdict.verdict_title`, `verdict.definitive_ruling`, `verdict.alignment_status`
- `verdict.majority_response`, `verdict.dissenting_perspectives[]`, `verdict.actionable_guidance[]`
- `verdict.framework_convictions.{utilitarianism|deontology|care_ethics|virtue_ethics}.{action,weight,rationale}`
- per-framework objects: `recommended_action`, `conviction_score`, `conviction_rationale`

The `/api/*` routes without `v1` are kept for the bundled web UI and AMA 2.x clients.
