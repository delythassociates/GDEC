from __future__ import annotations
import json
from pathlib import Path
from dses_v06 import build_certificate, summarize_certificate, uniform_grid, verify_certificate

ROOT=Path(__file__).resolve().parents[1]
results={}
for uncertainty in ("correlated_disk","independent_box_outer"):
    cert=build_certificate(uncertainty,max_depth=12)
    results[uncertainty]={"adaptive":summarize_certificate(cert),
                          "uniform_64x64":uniform_grid(uncertainty,n=64),
                          "verification":verify_certificate(cert)}
    (ROOT/"results"/("DSES_V06_"+uncertainty.upper()+"_CERTIFICATE.json")).write_text(
        json.dumps(cert,indent=2,sort_keys=True),encoding="utf-8")
(ROOT/"results"/"DSES_V06_REPRODUCED_SUMMARIES.json").write_text(
    json.dumps(results,indent=2,sort_keys=True),encoding="utf-8")
print(json.dumps(results,indent=2,sort_keys=True))
