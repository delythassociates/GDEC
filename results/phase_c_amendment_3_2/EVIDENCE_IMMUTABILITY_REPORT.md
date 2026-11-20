# GDEC Phase C Amendment 3.2 — Evidence Immutability & Serialization Report

**Implementation:** `src/gdec/core/analyser.py` (`MeshLevelEvidence`, `_deep_freeze`, `_to_json_serializable`)  
**Governing Standard:** AM32-03 Deep Immutability and Evidence Integrity  
**Status:** **VERIFIED IMMUTABLE & DETERMINISTIC**  

---

## 1. Deep Immutability Architecture

To prevent false-positive verification through in-place tampering or shallow immutability bypasses, `MeshLevelEvidence` implements comprehensive deep immutability:

1. **Class-Level Immutability:** `@dataclass(frozen=True)` enforces that instance attributes cannot be assigned or deleted post-construction (`FrozenInstanceError`).
2. **Defensive Deep Copying:** In `__post_init__`, caller-supplied dictionaries and lists are defensively cloned. Subsequent mutations of caller variables do not affect the stored evidence.
3. **Recursive Freezing (`_deep_freeze`):**
   - Standard dictionaries are recursively converted into read-only `types.MappingProxyType` instances.
   - Lists are converted into immutable `tuple` instances.
   - Sets are converted into `frozenset`.
   - NumPy arrays are cloned and marked `flags.writeable = False`.
4. **No Mutation via Accessors:** All dictionary accessors return read-only mapping proxies. Attempting in-place item assignment (`ev.refinement_evidence['key'] = val`) raises `TypeError: 'mappingproxy' object does not support item assignment`.

---

## 2. Canonical Serialization & Hash Stability

To ensure evidence records can be reliably hashed, signed, and audited across processes:

1. **Deterministic Representation (`to_canonical_dict`):**
   - Keys are sorted lexicographically at every nesting depth.
   - Floats and ints are strictly cast to standard Python numeric types.
   - Boolean values are strictly normalized.
2. **Canonical Hash (`canonical_hash`):**
   - Produces a deterministic SHA-256 hash using compact separators `(',', ':')` and sorted keys.
   - Invariant to insertion order in caller dictionaries.
3. **Round-Trip Reconstruction (`from_canonical_dict`):**
   - Reconstructs a deeply immutable `MeshLevelEvidence` object matching the exact canonical hash of the source.

---

## 3. Adversarial Mutation Proof Matrix

| Attack Vector | Target Object | Expected Exception | Observed Behavior | Test Status |
|:-------------:|:-------------:|:------------------:|:-----------------:|:-----------:|
| Top-level attribute mutation | `ev.element_count = 16` | `FrozenInstanceError` | Raised `FrozenInstanceError` | **PASS** |
| Top-level attribute deletion | `del ev.level_id` | `FrozenInstanceError` | Raised `FrozenInstanceError` | **PASS** |
| Nested dictionary assignment | `ev.refinement_evidence['nested']['k'] = 1` | `TypeError` | Raised `TypeError: 'mappingproxy' does not support assignment` | **PASS** |
| Nested list appending | `ev.refinement_evidence['list'].append(1)` | `AttributeError` | Raised `AttributeError: 'tuple' has no attribute 'append'` | **PASS** |
| Caller reference mutation | `dict_ref['k'] = 'tampered'` | None (Defensive Copy) | Instance value unchanged | **PASS** |
| Key-order permutation hash | Dict with reordered keys | Identical Hash | Hashes match exactly | **PASS** |
| Round-trip deserialization | `dict -> hash -> dict` | Identical Hash | Hash invariant under roundtrip | **PASS** |