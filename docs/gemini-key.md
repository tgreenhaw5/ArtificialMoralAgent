# Get a free Gemini API key

ArtificialMoralAgent uses Google's **Gemini Flash-Lite** by default. A free key takes about two minutes and no
credit card. The same steps are in the app at `/help/gemini-key`.

1. Open **https://aistudio.google.com/apikey** and sign in with a Google account.
2. The first time, accept the Gemini API terms. The marketing checkbox is optional.
3. Click **Create API key**. If asked, choose *Create API key in new project*.
4. Copy the key straight away; it is shown in full only once. Keep it private, like a password.
5. Run `ama init` and paste it when asked, or add `GEMINI_API_KEY=…` to `~/.ama/.env`. Restart `ama serve`.
6. Check with `ama doctor`: *model reachable* and *embeddings* should say PASS.

**Privacy on the free tier.** Google may use data sent through free-tier keys to improve its products. While
you use a free key, avoid putting confidential or identifying details into dilemmas. Alternatively, use a
paid key, or the `local` preset with Ollama, where nothing leaves your computer. Free-tier use is
rate-limited rather than billed.
