# GDEC Versioning and Compatibility Policy

**Document ID:** `GDEC-POL-001`  
**Status:** Baselined  
**Date:** 2026-11-22  
**Target Version:** `0.3.0-alpha` (`0.3.0a0`)

---

## 1. Principles of Versioning

GDEC uses [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html) as its version format. While the project remains at `0.y.z`, the SemVer specification treats the public API as unstable; compatibility commitments below are project goals, not a claim that pre-1.0 releases have stable APIs.

Platform versions follow the format:
```text
MAJOR.MINOR.PATCH[-PRERELEASE]
```
- **MAJOR (0.x -> 1.x):** Breaking API changes, non-backward-compatible changes to language syntax, or structural rewrites of the core execution protocols.
- **MINOR (x.1 -> x.2):** Backward-compatible additions of physical models (e.g. heat conduction), execution backends, estimators, or IR capabilities.
- **PATCH (x.x.1 -> x.x.2):** Bug fixes, numerical correctness remediations, performance enhancements, and documentation corrections with zero API breaks.
- **PRERELEASE (`0.3.0a0` / `0.3.0-alpha`):** Active development versions undergoing research, adversarial hardening, or validation passes.

---

## 2. Decoupled Schema Versioning

To ensure that engineering data, simulation certificates, and intermediate representations outlive specific Python runtime packages, **schema versions are strictly decoupled from library release versions**.

### Document Schemas

| Artifact | Schema Identifier Field | Current Active Version | Specification Source |
|---|---|---|---|
| **Legacy Problem IR** | `schema_version` | `"gdec_ir_v0.1"` | `src/gdec/language/ir.py` |
| **Canonical Engineering IR (EIR)** | `schema_version` | `"0.1.0"` | `src/gdec/eir/models.py` |
| **Decision Contract** | `schema_version` | `"1.0.0"` | `src/gdec/dse/contract.py` |
| **Benchmark / Verification Report** | `report_schema_version` | `"gdec_report_v0.2"` | `src/gdec/benchmark/reporting.py` |
| **Evidence Record (WP3)** | `evidence_schema_version` | `"1.0.0"` | `src/gdec/dse/evidence.py` |

### Version Appearance in Files

1. **Intermediate Representation (IR):**
   ```json
   {
     "schema_version": "0.1.0",
     "generator": "gdec",
     "generator_version": "0.3.0a0",
     "problem_id": "cantilever_beam",
     ...
   }
   ```
2. **Simulation Result & Evidence Files:**
   ```json
   {
     "schema_version": "1.0.0",
     "engine_version": "0.3.0a0",
     "timestamp": "2026-11-22T23:00:00Z",
     "eir_hash": "sha256:...",
     "qoi_result": { ... },
     "evidence_record": { ... }
   }
   ```

---

## 3. Backward Compatibility & Migration Guarantees

1. **IR Invariant:** GDEC guarantees that valid saved IR files from earlier minor versions will continue to load or will trigger an explicit, typed migration routine with descriptive error guidance.
2. **Deprecation Notice Period:** Any API or IR field designated for removal must be deprecated for at least one minor release cycle (`>= 1 minor version`) before elimination.
3. **Refusal Over Silent Coercion:** If an older file lacks fields required for strict verification under a newer schema, GDEC explicitly refuses rather than silently fabricating default values.
