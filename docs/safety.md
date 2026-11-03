# Safety and limitations

**Always on, not configurable:**
- Every dilemma passes a **safety triage** before any analysis. Possible self-harm, imminent violence or
  abuse gets crisis resources (988, emergency services, findahelpline.com) instead of an ethical analysis.
- If the triage model is unavailable, a **local check** for crisis language runs instead. A dilemma that
  trips it gets the crisis response.
- **Every response carries the disclaimer**: in the UI footer, under each result, in API responses, and in
  MCP tool results.
- **User text is fenced as data** in every prompt. Instructions inside a dilemma are ignored.

**Limitations to keep in mind:**
- The frameworks are simplified models of rich traditions, written as prompts. The six sages are "inspired
  by" figures; they do not speak for them or for any religion.
- Language models carry biases from their training data and can be confidently wrong. Conviction scores
  are model judgments, not measurements.
- Results vary between models and between runs. Each evaluation records its model and prompt version.
- ArtificialMoralAgent supports a human decision. It must not be used as the sole basis for decisions about
  people's rights, health, employment, liberty or safety.

**Privacy:**
- Guest evaluations are private until an admin publishes them.
- Free-tier model keys may let the provider use the data you send (see [Gemini key](gemini-key.md)).
- The `local` preset keeps everything on your machine.
