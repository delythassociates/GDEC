from __future__ import annotations
import copy
from hashlib import sha256
import pytest
from dses_v06 import (Q,build_certificate,canonical_json,classify_regret_interval,
                      summarize_certificate,uniform_grid,verify_certificate)


@pytest.mark.parametrize("uncertainty",["correlated_disk","independent_box_outer"])
def test_certificate_round_trip_and_exact_area_coverage(uncertainty):
    cert=build_certificate(uncertainty,max_depth=8)
    report=verify_certificate(cert)
    assert report["valid"] is True
    assert report["errors"]==[]
    assert sum(Q(v) for v in report["classification_area"].values())==1


def test_disk_support_is_tighter_than_independent_outer_box():
    from dses_v06 import support_upper
    rect=(Q(1,3),Q(2,3),Q(1,4),Q(3,4))
    assert support_upper(*rect,"correlated_disk") < support_upper(*rect,"independent_box_outer")


def test_regret_logic_three_way_and_refusal_is_not_ambiguous():
    margin=Q(3,20)
    assert classify_regret_interval(Q(-1),-margin)=="SELECT_A"
    assert classify_regret_interval(margin,Q(1))=="SELECT_B"
    assert classify_regret_interval(Q(-1,10),Q(1,10))=="REFUSE_HIGH_REGRET"
    assert classify_regret_interval(Q(-1,5),Q(1,10))=="UNRESOLVED"


def test_tamper_rejected_even_after_attacker_recomputes_digest():
    cert=build_certificate("correlated_disk",max_depth=6)
    bad=copy.deepcopy(cert); bad["leaf_count"]+=1
    unsigned={k:v for k,v in bad.items() if k!="certificate_sha256"}
    bad["certificate_sha256"]=sha256(canonical_json(unsigned).encode()).hexdigest()
    report=verify_certificate(bad)
    assert report["valid"] is False
    assert "CERT-LEAF-COUNT-MISMATCH" in report["errors"]


def test_changed_split_boundary_rejected_even_after_rehash():
    cert=build_certificate("correlated_disk",max_depth=8)
    bad=copy.deepcopy(cert); bad["tree"]["mid"]="1/3"
    unsigned={k:v for k,v in bad.items() if k!="certificate_sha256"}
    bad["certificate_sha256"]=sha256(canonical_json(unsigned).encode()).hexdigest()
    report=verify_certificate(bad)
    assert report["valid"] is False
    assert "CERT-RECTANGLE-PARTITION-MISMATCH" in report["errors"]


def test_uniform_and_adaptive_correlated_partition_match_exact_areas():
    adaptive=summarize_certificate(build_certificate("correlated_disk",max_depth=12))
    uniform=uniform_grid("correlated_disk",n=64)
    assert adaptive["area_fraction"]==uniform["area_fraction"]
    assert adaptive["leaf_count"]<uniform["cells"]


def test_rectangular_outer_bound_does_not_claim_more_acceptance_than_disk():
    disk=summarize_certificate(build_certificate("correlated_disk",max_depth=12))
    box=summarize_certificate(build_certificate("independent_box_outer",max_depth=12))
    assert box["area_percent"]["SELECT_A"]<=disk["area_percent"]["SELECT_A"]
    assert box["area_percent"]["SELECT_B"]<=disk["area_percent"]["SELECT_B"]
    assert box["area_percent"].get("REFUSE_HIGH_REGRET",0.0)<=disk["area_percent"].get("REFUSE_HIGH_REGRET",0.0)
    assert box["area_percent"]["UNRESOLVED"]>=disk["area_percent"]["UNRESOLVED"]


def test_certificate_rejects_altered_model_identity():
    cert=build_certificate("correlated_disk",max_depth=4)
    bad=copy.deepcopy(cert); bad["model_id"]="different-model"
    report=verify_certificate(bad)
    assert report["valid"] is False
    assert "CERT-HASH-MISMATCH" in report["errors"]
    assert "CERT-MODEL-MISMATCH" in report["errors"]


def test_malformed_nonfinite_payload_returns_structured_failure():
    cert=build_certificate("correlated_disk",max_depth=4)
    bad=copy.deepcopy(cert); bad["unexpected"]=float("nan")
    report=verify_certificate(bad)
    assert report["valid"] is False
    assert report["errors"]==["CERT-CANONICALIZATION-FAILED"]
