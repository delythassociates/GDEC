# Security Policy for GDEC

## Scope and Principles
GDEC is computational mechanics and scientific software intended for engineering analysis. Security in GDEC focuses on:
1. Deterministic and safe execution of models without arbitrary code injection.
2. Safe parsing of engineering specifications (`.gdc`) and Intermediate Representation documents (`.json`).
3. Refusal to evaluate or export unverified or tampered engineering data.

## Supported Versions
Security fixes are developed on active research branches. Release support is subject to maintainer review; branch names are not independently versioned releases:

| Version | Supported | Notes |
|---|---|---|
| `0.3.0a0` (pre-release development snapshot) | Development only | No stable release support commitment; fixes are applied to the relevant maintained branch |
| `0.2.2` | Critical fixes only | Legacy evaluation baseline |
| `< 0.2.2` | No | Historical research prototypes |

## Reporting Vulnerabilities
If you discover a security vulnerability, input parsing flaw that permits arbitrary execution, or cryptographic hash collision vulnerability:
- Do not open a public issue.
- Use GitHub private vulnerability reporting / Security Advisories if enabled for this repository.
- Otherwise, contact maintainers privately through a verified contact route published by the organization. Include a minimal reproduction where safe. No acknowledgement-time SLA is currently published.
