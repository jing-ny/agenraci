# Security Policy

## Scope

AgenRACI is a command-line tool that **reads and checks** a YAML charter file. It does
not run as a network service, does not execute the charters it reads, and does not act on
your systems at runtime — so its attack surface is small. The most relevant concerns are
the usual ones for a Python package and YAML parser: handling untrusted input safely and
keeping dependencies current.

## Supported versions

Security fixes target the latest released `0.1.x` line on PyPI. Older pre-release
versions (e.g. `0.1.0a0`) are not supported.

| Version | Supported |
| ------- | --------- |
| 0.1.x   | ✅        |
| < 0.1.0 | ❌        |

## Reporting a vulnerability

Please report security issues **privately** — do not open a public issue for a suspected
vulnerability.

Use GitHub's private vulnerability reporting:

1. Go to the **[Security tab](https://github.com/jing-ny/agenraci/security)** of the repo.
2. Click **Report a vulnerability**.
3. Describe the issue, how to reproduce it, and the impact you expect.

This channel is visible only to the maintainers. We aim to acknowledge a report within a
few days and will coordinate a fix and disclosure timeline with you. Thank you for helping
keep AgenRACI and its users safe.
