# Security Guide

This fork prioritizes conservative defaults for unattended and low-resource deployments.

## Threat model

Assume an attacker may try to:

- Exfiltrate API keys or secrets from config, environment, or shell history.
- Induce high-cost prompt loops (token abuse / budget drain).
- Escalate via broad tool access (filesystem, shell, network fetchers).
- Abuse overly-privileged container runtime settings.

Primary defenses:

- Local-only service binds by default (`127.0.0.1`).
- Workspace scoping and shell sandboxing for tool execution.
- Budget caps that bound per-request/session/day token burn.
- Principle of least privilege in Docker and host permissions.

## Key management guidance

- Prefer environment variables or secret managers over hardcoding keys in committed files.
- Store `~/.nanobot/config.json` with strict file permissions (`chmod 600`).
- Use one key per environment (dev/staging/prod) to contain blast radius.
- Avoid sharing keys across independent bots or channels.
- Treat logs and crash dumps as potentially sensitive.

## Rotation workflow

1. Create a new provider key in your provider console.
2. Update secret store or `config.json` on host.
3. Restart nanobot process(es) gracefully.
4. Verify health (`nanobot agent` test prompt).
5. Revoke the old key.
6. Record rotation date and owner in ops notes.

Recommended cadence: every 30-90 days, or immediately after suspected leakage.

## Incident response basics

If compromise is suspected:

1. **Contain**: stop running agents/gateway; disable compromised credentials.
2. **Preserve evidence**: retain relevant logs/config snapshots securely.
3. **Eradicate**: rotate all related secrets; patch misconfiguration.
4. **Recover**: redeploy from known-good config and minimal privileges.
5. **Review**: document root cause and hardening follow-ups.

For routine operations, pair this guide with the deployment hardening notes in `docs/deployment.md`.
