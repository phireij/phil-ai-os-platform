# Phase 2.1C — Operator Authentication Secret Setup

**Program:** Phil AI OS Platform  
**Date:** 2026-08-26  
**Purpose:** one-time protected credential setup required before authenticated operator-dashboard activation

## Required GitHub Actions secret

Create exactly one new repository secret:

`MC_BASIC_AUTH_HASH`

The value must be a Traefik-compatible BasicAuth `users` entry in the form:

```text
operator:<password-hash>
```

Use a strong, unique password that is not used for GitHub, VPS SSH, OpenAI, Telegram, Hermes, Hostinger, or any other account.

## Recommended generation method

Generate the hash locally or on the VPS without committing the cleartext password or hash to Git history.

Using `htpasswd` where available:

```bash
htpasswd -nbB operator 'YOUR-STRONG-UNIQUE-PASSWORD'
```

The command prints one line beginning with `operator:`. Store that complete line as the GitHub repository secret `MC_BASIC_AUTH_HASH`.

If `htpasswd` is not available, install/use an equivalent bcrypt-capable password-hash utility outside the public repository. Do not use plaintext BasicAuth credentials in compose labels.

## GitHub UI location

Repository:

`phireij/phil-ai-os-platform`

Then:

`Settings -> Secrets and variables -> Actions -> New repository secret`

Name:

`MC_BASIC_AUTH_HASH`

Value:

The complete `operator:<bcrypt-hash>` line.

## Security rules

- Never commit the cleartext password.
- Never commit the generated BasicAuth hash to this public repository.
- Never reuse the Control API bearer token or any provider/Telegram/SSH credential.
- Do not send the password through Telegram approval messages.
- Keep the cleartext password in the operator's password manager.
- Rotate the secret by replacing `MC_BASIC_AUTH_HASH` and redeploying only the operator route.

## What happens next

Once `MC_BASIC_AUTH_HASH` exists, run:

`Phase 2.1C Authenticated Exposure Activation Preflight`

The preflight will fail closed unless:

- authentication material is present;
- existing approval and Mission Control routes are unchanged;
- `general` remains the only production execution class;
- monitoring/backups/self-heal are healthy;
- the operator route is not already present;
- port 4881 is not publicly listening.

No public route is activated by the preflight itself.

`PHIL_AI_OS_PHASE_2_1C_OPERATOR_AUTH_SECRET_SETUP_DEFINED`
