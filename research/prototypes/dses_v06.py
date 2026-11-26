"""DSES v0.6: correlation-aware robust-regret design-space partitioning.

Analytical research prototype only. Bounds use exact rational arithmetic;
this is neither a finite-element solver nor a general proof system.
"""
from __future__ import annotations
from fractions import Fraction
from hashlib import sha256
from math import isqrt
import json
from typing import Any, Dict, Iterable, List, Tuple

Q = Fraction
TAU = Q(35, 100)
REGRET_OFFSET = Q(1, 2)
MARGIN = REGRET_OFFSET - TAU
SQRT_SCALE = 10**6
MODEL_ID = "dSES-correlated-regret-analytical-v06"
DOMAIN = (Q(0), Q(1), Q(0), Q(1))


def _f(v: Q) -> str:
    return f"{v.numerator}/{v.denominator}"


def _parse(v: str) -> Q:
    a, b = v.split("/")
    return Q(int(a), int(b))


def ceil_sqrt_fraction(q: Q, scale: int = SQRT_SCALE) -> Q:
    """Smallest k/scale whose square is >= q, using exact integer arithmetic."""
    if q < 0:
        raise ValueError("square-root input must be non-negative")
    if q == 0:
        return Q(0)
    k = isqrt((q.numerator * scale * scale) // q.denominator)
    while Q(k*k, scale*scale) < q:
        k += 1
    return Q(k, scale)


def base_value(x: Q, y: Q) -> Q:
    return 2*x - y - Q(1, 2) + Q(1, 10)*x*y


def uncertainty_coefficients(x: Q, y: Q, scale: Q = Q(1)) -> Tuple[Q, Q]:
    return scale*Q(8, 100)*(1+x/Q(4)), scale*Q(5, 100)*(1-Q(3, 20)*y)


def base_range(xlo: Q, xhi: Q, ylo: Q, yhi: Q) -> Tuple[Q, Q]:
    # dc/dx=2+0.1y > 0 and dc/dy=-1+0.1x < 0 on [0,1]^2.
    return base_value(xlo, yhi), base_value(xhi, ylo)


def support_upper(xlo: Q, xhi: Q, ylo: Q, yhi: Q,
                  uncertainty: str, scale: Q = Q(1)) -> Q:
    a, b = uncertainty_coefficients(xhi, ylo, scale)
    if uncertainty == "correlated_disk":
        return ceil_sqrt_fraction(a*a+b*b)
    if uncertainty == "independent_box_outer":
        return a+b
    raise ValueError("unknown uncertainty set: " + uncertainty)


def regret_enclosure(xlo: Q, xhi: Q, ylo: Q, yhi: Q,
                     uncertainty: str, scale: Q = Q(1)) -> Tuple[Q, Q]:
    c_lo, c_hi = base_range(xlo, xhi, ylo, yhi)
    u = support_upper(xlo, xhi, ylo, yhi, uncertainty, scale)
    return c_lo-u, c_hi+u


def classify_regret_interval(dlo: Q, dhi: Q) -> str:
    if dlo > dhi:
        raise ValueError("invalid enclosure")
    if dhi <= -MARGIN:
        return "SELECT_A"
    if dlo >= MARGIN:
        return "SELECT_B"
    if dlo > -MARGIN and dhi < MARGIN:
        return "REFUSE_HIGH_REGRET"
    return "UNRESOLVED"


def classify_cell(rect: Tuple[Q,Q,Q,Q], uncertainty: str, scale: Q = Q(1)):
    xlo,xhi,ylo,yhi = rect
    dlo,dhi = regret_enclosure(xlo,xhi,ylo,yhi,uncertainty,scale)
    return classify_regret_interval(dlo,dhi),(dlo,dhi)


def _rect_json(rect):
    return [_f(v) for v in rect]


def _node(rect, depth, uncertainty, scale, max_depth):
    cls,(dlo,dhi)=classify_cell(rect,uncertainty,scale)
    xlo,xhi,ylo,yhi=rect
    node={"rect":_rect_json(rect),"depth":depth}
    if cls!="UNRESOLVED" or depth>=max_depth:
        node.update({"kind":"leaf","classification":cls,"d_interval":[_f(dlo),_f(dhi)],
                     "support_upper":_f(support_upper(*rect,uncertainty,scale))})
        return node
    axis="x" if (xhi-xlo)>=(yhi-ylo) else "y"
    if axis=="x":
        mid=(xlo+xhi)/2
        left=(xlo,mid,ylo,yhi); right=(mid,xhi,ylo,yhi)
    else:
        mid=(ylo+yhi)/2
        left=(xlo,xhi,ylo,mid); right=(xlo,xhi,mid,yhi)
    node.update({"kind":"split","axis":axis,"mid":_f(mid),
                 "children":[_node(left,depth+1,uncertainty,scale,max_depth),
                             _node(right,depth+1,uncertainty,scale,max_depth)]})
    return node


def _walk_leaves(node):
    if node["kind"]=="leaf":
        yield node
    else:
        for child in node["children"]:
            yield from _walk_leaves(child)


def _count_nodes(node):
    if node["kind"]=="leaf":
        return 1,1
    a,b=_count_nodes(node["children"][0]); c,d=_count_nodes(node["children"][1])
    return 1+a+c,b+d


def canonical_json(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False)


def build_certificate(uncertainty="correlated_disk",max_depth=12,scale:Q=Q(1)):
    if max_depth<0 or max_depth>24:
        raise ValueError("max_depth must be in [0,24]")
    tree=_node(DOMAIN,0,uncertainty,scale,max_depth)
    nodes,leaves=_count_nodes(tree)
    payload={
        "schema_version":"dses_certificate_v0.6",
        "model_id":MODEL_ID,
        "assurance_class":"ANALYTICAL_EXACT_RATIONAL_ENCLOSURE",
        "uncertainty_set":uncertainty,
        "uncertainty_scale":_f(scale),
        "design_domain":_rect_json(DOMAIN),
        "regret_contract":{"tau":_f(TAU),"offset":_f(REGRET_OFFSET),
          "selection_margin":_f(MARGIN),"R_A":"max(0, D + 1/2)","R_B":"max(0, 1/2 - D)"},
        "proof_rule_version":"v0.6.1","sqrt_upper_scale":SQRT_SCALE,
        "max_depth":max_depth,"node_count":nodes,"leaf_count":leaves,"tree":tree,
        "hash_non_claim":"SHA-256 detects payload changes relative to this digest; it does not authenticate the producer or establish physical-model validity."
    }
    payload["certificate_sha256"]=sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return payload


def verify_certificate(cert: Dict[str,Any]) -> Dict[str,Any]:
    """Recompute semantic tree invariants, leaf bounds, area, counts and digest."""
    if not isinstance(cert,dict):
        return {"valid":False,"errors":["certificate must be an object"]}
    errors=[]
    try:
        unsigned={k:v for k,v in cert.items() if k!="certificate_sha256"}
        digest=sha256(canonical_json(unsigned).encode("utf-8")).hexdigest()
    except (TypeError,ValueError,RecursionError):
        return {"valid":False,"errors":["CERT-CANONICALIZATION-FAILED"]}
    if cert.get("certificate_sha256")!=digest: errors.append("CERT-HASH-MISMATCH")
    if cert.get("schema_version")!="dses_certificate_v0.6": errors.append("CERT-SCHEMA-UNSUPPORTED")
    if cert.get("model_id")!=MODEL_ID: errors.append("CERT-MODEL-MISMATCH")
    uncertainty=cert.get("uncertainty_set")
    if uncertainty not in {"correlated_disk","independent_box_outer"}:
        errors.append("CERT-UNCERTAINTY-UNSUPPORTED")
    try:
        depth=int(cert["max_depth"])
        if depth<0 or depth>24: errors.append("CERT-DEPTH-LIMIT-EXCEEDED")
        if len(canonical_json(cert))>20_000_000: errors.append("CERT-SIZE-LIMIT-EXCEEDED")
        scale=_parse(cert["uncertainty_scale"])
        if scale<=0: errors.append("CERT-SCALE-INVALID")
        if cert["design_domain"]!=_rect_json(DOMAIN): errors.append("CERT-DOMAIN-MISMATCH")
        expected_contract={"tau":_f(TAU),"offset":_f(REGRET_OFFSET),"selection_margin":_f(MARGIN),
                           "R_A":"max(0, D + 1/2)","R_B":"max(0, 1/2 - D)"}
        if cert["regret_contract"]!=expected_contract: errors.append("CERT-REGRET-CONTRACT-MISMATCH")
        leaves=list(_walk_leaves(cert["tree"]))
        if len(leaves)!=int(cert["leaf_count"]): errors.append("CERT-LEAF-COUNT-MISMATCH")
        node_count,leaf_count=_count_nodes(cert["tree"])
        if node_count!=int(cert["node_count"]) or leaf_count!=int(cert["leaf_count"]):
            errors.append("CERT-NODE-COUNT-MISMATCH")
        def check_node(n,expected):
            if tuple(_parse(v) for v in n["rect"])!=expected:
                errors.append("CERT-RECTANGLE-PARTITION-MISMATCH"); return
            if n["kind"]=="leaf":
                cls,(lo,hi)=classify_cell(expected,uncertainty,scale)
                if n.get("classification")!=cls: errors.append("CERT-CLASSIFICATION-MISMATCH")
                if n.get("d_interval")!=[_f(lo),_f(hi)]: errors.append("CERT-ENCLOSURE-MISMATCH")
                if n.get("support_upper")!=_f(support_upper(*expected,uncertainty,scale)):
                    errors.append("CERT-SUPPORT-BOUND-MISMATCH")
                return
            if n["kind"]!="split" or len(n["children"])!=2:
                errors.append("CERT-TREE-NODE-INVALID"); return
            x0,x1,y0,y1=expected; mid=_parse(n["mid"])
            if n["axis"]=="x" and x0<mid<x1:
                a=(x0,mid,y0,y1); b=(mid,x1,y0,y1)
            elif n["axis"]=="y" and y0<mid<y1:
                a=(x0,x1,y0,mid); b=(x0,x1,mid,y1)
            else:
                errors.append("CERT-SPLIT-INVALID"); return
            check_node(n["children"][0],a); check_node(n["children"][1],b)
        check_node(cert["tree"],DOMAIN)
        areas={}
        for leaf in leaves:
            x0,x1,y0,y1=(_parse(v) for v in leaf["rect"])
            area=(x1-x0)*(y1-y0); cls=leaf["classification"]
            areas[cls]=areas.get(cls,Q(0))+area
        if sum(areas.values(),Q(0))!=1: errors.append("CERT-AREA-COVERAGE-FAILED")
        return {"valid":not errors,"errors":sorted(set(errors)),"certificate_sha256":digest,
                "node_count":node_count,"leaf_count":leaf_count,
                "classification_area":{k:_f(v) for k,v in sorted(areas.items())}}
    except (KeyError,ValueError,TypeError,ZeroDivisionError,IndexError,RecursionError) as exc:
        errors.append("CERT-MALFORMED:"+type(exc).__name__)
        return {"valid":False,"errors":sorted(set(errors))}


def uniform_grid(uncertainty,n=64,scale:Q=Q(1)):
    if n<=0: raise ValueError("n must be positive")
    step=Q(1,n); counts={}; areas={}
    for i in range(n):
        for j in range(n):
            rect=(Q(i,n),Q(i+1,n),Q(j,n),Q(j+1,n))
            cls,_=classify_cell(rect,uncertainty,scale)
            counts[cls]=counts.get(cls,0)+1
            areas[cls]=areas.get(cls,Q(0))+step*step
    return {"cells":n*n,"counts":counts,"area_fraction":{k:_f(v) for k,v in sorted(areas.items())}}


def summarize_certificate(cert):
    areas={}; counts={}
    for leaf in _walk_leaves(cert["tree"]):
        x0,x1,y0,y1=(_parse(v) for v in leaf["rect"])
        area=(x1-x0)*(y1-y0); cls=leaf["classification"]
        areas[cls]=areas.get(cls,Q(0))+area; counts[cls]=counts.get(cls,0)+1
    return {"node_count":cert["node_count"],"leaf_count":cert["leaf_count"],"counts":counts,
      "area_fraction":{k:_f(v) for k,v in sorted(areas.items())},
      "area_percent":{k:float(v*100) for k,v in sorted(areas.items())},
      "certificate_sha256":cert["certificate_sha256"]}
