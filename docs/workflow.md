# Collaboration workflow

`main` is protected: nothing gets pushed to it directly. Every change —
code, docs, config — goes through a pull request.

## The flow

1. Create a branch from `main` (`feat/...`, `fix/...`, `docs/...`).
2. Commit your changes to the branch.
3. Open a pull request against `main`.
4. Merge only when the diff looks right. No bypassing, no exceptions —
   the rule applies to everyone, including repo admins.

## Secrets

- Camera stream URLs and RTSP passwords live in a local `.env` file on the
  machine running the monitor. `.env` is gitignored — it is never committed.
- `config/cameras.yaml` holds everything else (host, port, path, username)
  and references passwords via `password_env`.
- `.env.example` at the repo root documents the required variables.
- Never paste credentials into chat, issues, or PR descriptions.

## Roles

- **Clockcode** writes the code.
- **Jarvis** (project manager) keeps requirements coherent, reviews code
  against the BRD, tracks work in GTD, and routes owner decisions to Bowen.
- **Bowen** owns the repo and merges pull requests.
