from __future__ import annotations

import copy
from hashlib import sha256

import pytest

from research.prototypes.dses_v06 import (
    build_certificate,
    canonical_json,
    verify_certificate,
)


def _rehash(cert):
    unsigned = {k: v for k, v in cert.items() if k != "certificate_sha256"}
    cert["certificate_sha256"] = sha256(canonical_json(unsigned).encode("utf-8")).hexdigest()
    return cert


@pytest.mark.parametrize(
    ("field", "value", "expected_error"),
    [
        ("assurance_class", "PHYSICALLY_CERTIFIED", "CERT-ASSURANCE-CLASS-UNSUPPORTED"),
        ("proof_rule_version", "v999", "CERT-PROOF-RULE-UNSUPPORTED"),
        ("sqrt_upper_scale", 1, "CERT-SQRT-SCALE-UNSUPPORTED"),
    ],
)
def test_rejects_unsupported_proof_metadata_even_after_rehash(field, value, expected_error):
    cert = copy.deepcopy(build_certificate("correlated_disk", max_depth=5))
    cert[field] = value
    _rehash(cert)
    report = verify_certificate(cert)
    assert report["valid"] is False
    assert expected_error in report["errors"]


def test_rejects_lied_about_maximum_tree_depth_even_after_rehash():
    cert = copy.deepcopy(build_certificate("correlated_disk", max_depth=8))
    cert["max_depth"] = 0
    _rehash(cert)
    report = verify_certificate(cert)
    assert report["valid"] is False
    assert "CERT-TREE-DEPTH-EXCEEDED" in report["errors"]


def test_rejects_node_depth_metadata_mismatch_even_after_rehash():
    cert = copy.deepcopy(build_certificate("correlated_disk", max_depth=8))
    assert cert["tree"]["kind"] == "split"
    cert["tree"]["children"][0]["depth"] = 99
    _rehash(cert)
    report = verify_certificate(cert)
    assert report["valid"] is False
    assert "CERT-NODE-DEPTH-MISMATCH" in report["errors"]


def test_rejects_boolean_max_depth():
    cert = copy.deepcopy(build_certificate("correlated_disk", max_depth=4))
    cert["max_depth"] = True
    _rehash(cert)
    report = verify_certificate(cert)
    assert report["valid"] is False
    assert any("CERT-MALFORMED" in error for error in report["errors"])
