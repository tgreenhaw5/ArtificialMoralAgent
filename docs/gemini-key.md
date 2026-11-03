# Get a free Gemini API key

ArtificialMoralAgent uses Google's **Gemini Flash-Lite** by default. You can get a free key in about a minute,
with no credit card, from [Google AI Studio](https://aistudio.google.com/app/apikey). The same steps are in the
app at `/help/gemini-key`.

## How to get it

1. **Sign in:** go to [Google AI Studio](https://aistudio.google.com/app/apikey) and sign in with your Google account.
2. **Accept the terms:** the first time, accept the terms of service.
3. **Create a key:** click **Get API key** in the sidebar or top menu, then click **Create API key**.
4. **Copy it:** copy the key straight away and keep it private, like a password.

## Use it with ArtificialMoralAgent

1. Run `ama init` and paste the key when asked, or add `GEMINI_API_KEY=…` to `~/.ama/.env`. Restart `ama serve`.
2. Check with `ama doctor`: *model reachable* and *embeddings* should say PASS.

## Good to know

- **Cost:** free. The free tier needs no credit card or billing account.
- **Limits:** per-minute and daily request and token limits. The free tier is meant for prototyping and testing,
  not heavy production use. A public demo should keep AMA's own daily limits on (see
  [Self-hosting](self-hosting.md)).
- **Privacy:** Google may use free-tier inputs and outputs to improve its models. Avoid putting sensitive or
  private details into dilemmas while using a free key. For private use, use a paid key, or the `local` preset
  with Ollama, where nothing leaves your computer.

Prefer to watch? [A short video shows how to create a free key in Google AI Studio](https://www.youtube.com/watch?v=prrb0hsfI60).
