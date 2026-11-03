# Security policy

Please report vulnerabilities privately through GitHub's **Report a vulnerability** button (Security tab), not in public issues.
We aim to acknowledge reports within 5 days.

In scope:
- authentication, API keys and sessions;
- ways around the public-demo limits or the safety triage;
- prompt injection that changes the analysis or exposes data;
- data exposure (unpublished dilemmas, keys).

Secrets never belong in the repository. CI runs gitleaks on every push, and a pre-commit hook is provided
(`pre-commit install`).
