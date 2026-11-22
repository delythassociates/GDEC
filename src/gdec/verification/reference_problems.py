"""
Traceable reference-problem library for GDEC verification and validation (V&V).
Contains eight traceable reference problems with exact mathematical formulations,
boundary conditions, expected values, tolerances, literature citations, and limitations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple
import math
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import skfem
from skfem.models.elasticity import linear_elasticity, plane_stress


@dataclass(frozen=True)
class ReferenceProblemSpec:
    """Specification of a traceable verification/validation problem."""
    problem_id: str
    name: str
    category: str  # 'numerical_verification', 'physical_validation', 'benchmark'
    source_reference: str
    governing_equations: str
    domain_description: str
    boundary_conditions: str
    expected_qoi_formula: str
    expected_order_h: Optional[float]
    expected_tolerance: str
    limitations: str
    cross_check_target: str


REFERENCE_PROBLEMS: Dict[str, ReferenceProblemSpec] = {
    "REF-01-PATCH-TEST": ReferenceProblemSpec(
        problem_id="REF-01-PATCH-TEST",
        name="Linear Displacement Constant Strain Patch Test",
        category="numerical_verification",
        source_reference="Irons & Razzaque (1972); Zienkiewicz & Taylor (6th ed., Vol 1)",
        governing_equations="div(sigma) = 0, sigma = C : eps, u = c1*x + c2*y + c0, v = d1*x + d2*y + d0",
        domain_description="Unit square [0, 1]^2 with intentionally distorted interior nodes",
        boundary_conditions="Exact linear displacement prescribed on all exterior boundaries",
        expected_qoi_formula="max |u_h - u_exact| == 0 to machine precision",
        expected_order_h=None,  # exact reproduction for degree p=1
        expected_tolerance="max_error <= 1e-11 m",
        limitations="2D linear elasticity, P1 triangular elements",
        cross_check_target="Analytical linear field; scikit-fem assembly",
    ),
    "REF-02-UNIAXIAL-TENSION": ReferenceProblemSpec(
        problem_id="REF-02-UNIAXIAL-TENSION",
        name="Uniform Uniaxial Tension Bar",
        category="physical_validation",
        source_reference="Timoshenko & Goodier, Theory of Elasticity (1970)",
        governing_equations="div(sigma) = 0, sigma_xx = sigma_0, sigma_yy = 0, sigma_xy = 0",
        domain_description="Rectangular bar [0, L] x [0, H] with L=4.0 m, H=1.0 m",
        boundary_conditions="Roller on left (u=0), center pinned (v=0), uniform normal traction t_x=sigma_0 on right",
        expected_qoi_formula="u_tip = sigma_0 * L / E, v(y) = -nu * sigma_0 * y / E",
        expected_order_h=None,  # exact reproduction for degree p=1
        expected_tolerance="relative_error <= 1e-10",
        limitations="Homogeneous isotropic material; plane stress",
        cross_check_target="Exact 1D/2D elasticity solution",
    ),
    "REF-03-TIMOSHENKO-CANTILEVER": ReferenceProblemSpec(
        problem_id="REF-03-TIMOSHENKO-CANTILEVER",
        name="Timoshenko Slender Cantilever Beam Bending",
        category="physical_validation",
        source_reference="Timoshenko & Goodier (1970), Section 35",
        governing_equations="div(sigma) = 0, plane stress elasticity with end shear load P",
        domain_description="Beam [0, L] x [-c, c] with L=4.0 m, depth D=2c=1.0 m, aspect ratio 4",
        boundary_conditions="Clamped kinematic root on left (x=0), parabolic shear traction on right (x=L)",
        expected_qoi_formula="v_tip = -(P*L^3)/(3*E*I) - (P*L*(4+5*nu))/(2*E*A*(1+nu))",
        expected_order_h=2.0,  # in L2 displacement norm under uniform refinement
        expected_tolerance="tip deflection within 1.5% on 65x33 mesh; converges from below",
        limitations="Shear-deformable 2D beam; P1 displacement formulation slightly stiff in bending",
        cross_check_target="Analytical Timoshenko 2D elasticity solution; scikit-fem reference",
    ),
    "REF-04-PURE-BENDING-MANUFACTURED": ReferenceProblemSpec(
        problem_id="REF-04-PURE-BENDING-MANUFACTURED",
        name="Exact Quadratic Displacement Pure Bending (MMS)",
        category="numerical_verification",
        source_reference="Szabo & Babuska, Finite Element Analysis (1991)",
        governing_equations="div(sigma) = 0 with u = -(M/(E*I))*x*y, v = (M/(2*E*I))*(x^2 + nu*y^2)",
        domain_description="Square or rectangular domain [0, 2] x [0, 1]",
        boundary_conditions="Exact quadratic Dirichlet displacement prescribed on all 4 boundaries",
        expected_qoi_formula="u_exact(x,y) and v_exact(x,y)",
        expected_order_h=2.0,  # L2 displacement error rate
        expected_tolerance="observed order p_obs in [1.85, 2.15] in L2 norm",
        limitations="Smooth harmonic displacement field; manufactured solution",
        cross_check_target="Closed-form manufactured displacement field",
    ),
    "REF-05-LAME-CYLINDER": ReferenceProblemSpec(
        problem_id="REF-05-LAME-CYLINDER",
        name="Lame Pressurized Thick Cylinder (Annulus)",
        category="physical_validation",
        source_reference="Lame (1852); Sadd, Elasticity: Theory, Applications, and Numerics (2020)",
        governing_equations="Radial equilibrium d(sigma_r)/dr + (sigma_r - sigma_theta)/r = 0",
        domain_description="Quadrant of thick cylinder a <= r <= b (a=1.0 m, b=2.0 m) in first quadrant",
        boundary_conditions="Internal pressure P_int on r=a, zero traction on r=b, symmetry rollers on x=0 and y=0",
        expected_qoi_formula="u_r(r) = ((1+nu)*P_int*a^2 / (E*(b^2 - a^2))) * ((1-2*nu)*r + b^2/r) [plane strain]",
        expected_order_h=2.0,
        expected_tolerance="discrepancy vs Lame formula <= 1.5% on moderate mesh",
        limitations="Curved boundary approximated by piecewise linear boundary segments",
        cross_check_target="Analytical Lame formula; scikit-fem curved quadrant",
    ),
    "REF-06-PLATE-HOLE-KIRSCH": ReferenceProblemSpec(
        problem_id="REF-06-PLATE-HOLE-KIRSCH",
        name="Kirsch Infinite Plate with Circular Hole (Stress Concentration)",
        category="physical_validation",
        source_reference="Kirsch (1898); Pilkey, Peterson's Stress Concentration Factors (2008)",
        governing_equations="Plane stress elastostatics with circular hole of radius a under far-field tension sigma_inf",
        domain_description="Finite quarter-plate [0, W] x [0, H] with hole radius a at origin, W >> a",
        boundary_conditions="Symmetry on x=0 and y=0, far-field traction on outer boundary, traction-free hole",
        expected_qoi_formula="Peak hoop stress sigma_theta(a, pi/2) == 3.0 * sigma_inf",
        expected_order_h=None,  # asymptotic stress concentration
        expected_tolerance="Peak stress concentration factor K_t in [2.90, 3.10]",
        limitations="Finite boundary approximation of infinite domain; P1 stress recovery smoothing",
        cross_check_target="Classical Kirsch analytical solution",
    ),
    "REF-07-L-SHAPED-DOMAIN-SINGULAR": ReferenceProblemSpec(
        problem_id="REF-07-L-SHAPED-DOMAIN-SINGULAR",
        name="L-Shaped Domain Re-Entrant Corner Singularity",
        category="numerical_verification",
        source_reference="Babuska & Rheinboldt (1978); Verfurth (1996)",
        governing_equations="div(sigma) = 0 on [-1, 1]^2 \\ (0, 1] x [-1, 0) with re-entrant corner (3*pi/2)",
        domain_description="L-shaped polygon with interior corner at (0,0)",
        boundary_conditions="Clamped or Dirichlet on exterior edges",
        expected_qoi_formula="Asymptotic corner singularity: displacement u ~ r^alpha with alpha approx 0.544",
        expected_order_h=0.544,  # degraded uniform order vs recovered adaptive order
        expected_tolerance="Uniform order < 1.0; Adaptive refinement recovers optimal error per DOF",
        limitations="Singular corner derivative; non-smooth solution space",
        cross_check_target="Goal-adaptive DWR estimator vs uniform baseline",
    ),
    "REF-08-RIGID-BODY-NULLSPACE": ReferenceProblemSpec(
        problem_id="REF-08-RIGID-BODY-NULLSPACE",
        name="Unconstrained Stiffness Matrix Nullspace Multiplicity",
        category="numerical_verification",
        source_reference="Bathe, Finite Element Procedures (1996)",
        governing_equations="K u_0 = 0 for rigid body motions (2 translations, 1 in-plane rotation)",
        domain_description="2D non-degenerate domain with free boundaries",
        boundary_conditions="Zero Dirichlet boundary conditions (completely unconstrained)",
        expected_qoi_formula="dim(null(K)) == 3, lambda_1 = lambda_2 = lambda_3 == 0.0",
        expected_order_h=None,
        expected_tolerance="lambda_3 <= 1e-12 * lambda_max, lambda_4 > 0.0",
        limitations="2D planar mechanics; 3 rigid body degrees of freedom",
        cross_check_target="Spectral nullity via dense/sparse ARPACK eigensolver",
    ),
}


def get_reference_problem(problem_id: str) -> ReferenceProblemSpec:
    """Retrieve specifications for a reference problem by ID."""
    if problem_id not in REFERENCE_PROBLEMS:
        raise KeyError(f"Unknown reference problem ID: '{problem_id}'. Valid IDs: {list(REFERENCE_PROBLEMS.keys())}")
    return REFERENCE_PROBLEMS[problem_id]


def list_reference_problems() -> List[ReferenceProblemSpec]:
    """Return all traceable reference problems in order."""
    return list(REFERENCE_PROBLEMS.values())
