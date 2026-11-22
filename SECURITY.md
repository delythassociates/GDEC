# Security Policy for GDEC

## Scope and Principles
GDEC is computational mechanics and scientific software intended for engineering analysis. Security in GDEC focuses on:
1. Deterministic and safe execution of models without arbitrary code injection.
2. Safe parsing of engineering specifications (`.gdc`) and Intermediate Representation documents (`.json`).
3. Refusal to evaluate or export unverified or tampered engineering data.

## Supported Versions
Security patches and verification fixes are provided for the active development branch:

| Version | Supported | Notes |
|---|---|---|
| `0.3.0-alpha` (`research/*`) | Yes | Active engineering development |
| `0.2.2` | Critical fixes only | Legacy evaluation baseline |
| `< 0.2.2` | No | Historical research prototypes |

## Reporting Vulnerabilities
If you discover a security vulnerability, input parsing flaw that permits arbitrary execution, or cryptographic hash collision vulnerability:
- Do not open a public issue.
- Email details to the engineering team at `security@delythassociates.com` with a reproducible test script.
- The engineering team will acknowledge within 48 hours and coordinate a verification patch.
