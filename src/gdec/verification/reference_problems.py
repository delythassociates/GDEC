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
        expected_qoi_formula="Plane stress: u_r(r) = (P_int*a^2/(E*(b^2-a^2)))*((1-nu)*r + (1+nu)*b^2/r); Plane strain: u_r(r) = ((1+nu)*P_int*a^2/(E*(b^2-a^2)))*((1-2*nu)*r + b^2/r)",
        expected_order_h=2.0,
        expected_tolerance="Observed area-weighted L2 convergence orders p_u in [1.85, 2.15], p_sigma in [0.85, 1.15]; max relative nodal displacement error <= 0.35%",
        limitations="Curved boundary discretized with linear chord facets; full analytical displacement and stress profiles (sigma_rr, sigma_theta, sigma_zz) verified for both plane stress and plane strain using area-weighted element L2 norms",
        cross_check_target="Authoritative closed-form Lame radial profiles; dual plane stress and plane strain FEM solves",
    ),
    "REF-06-PLATE-HOLE-KIRSCH": ReferenceProblemSpec(
        problem_id="REF-06-PLATE-HOLE-KIRSCH",
        name="Kirsch Infinite Plate with Circular Hole (Stress Concentration)",
        category="physical_validation",
        source_reference="Kirsch (1898); Pilkey, Peterson's Stress Concentration Factors (2008)",
        governing_equations="Plane stress elastostatics with circular hole of radius a under far-field tension sigma_inf",
        domain_description="Quarter-annulus / quadrant with hole radius a at origin, far-field radius b >> a",
        boundary_conditions="Symmetry on x=0 (u=0) and y=0 (v=0), far-field Kirsch traction on outer boundary r=b, traction-free hole r=a",
        expected_qoi_formula="Peak circumferential stress sigma_theta(a, pi/2) == sigma_xx(0, a) == 3.0 * sigma_inf; K_t = sigma_theta / sigma_inf == 3.0",
        expected_order_h=1.0,  # stress recovery convergence order in patch
        expected_tolerance="Mesh refinement series demonstrates K_t -> 3.000 monotonically with relative error <= 0.10% on fine mesh under area-weighted patch recovery",
        limitations="Piecewise linear approximation of circular cavity; area-weighted patch stress recovery at hole boundary (0, a) where theta=pi/2 aligns sigma_theta with sigma_xx",
        cross_check_target="Classical Kirsch analytical solution; mesh-refinement series, input traction sensitivity, and production defect sensitivity",
    ),
    "REF-07-L-SHAPED-DOMAIN-SINGULAR": ReferenceProblemSpec(
        problem_id="REF-07-L-SHAPED-DOMAIN-SINGULAR",
        name="L-Shaped Domain Re-Entrant Corner Singularity",
        category="numerical_verification",
        source_reference="Babuska & Rheinboldt (1978); Williams (1952); Verfurth (1996)",
        governing_equations="div(sigma) = 0 on [-1, 1]^2 \\ (0, 1] x [0, 1] with re-entrant corner (3*pi/2); Mode I corner singularity",
        domain_description="L-shaped polygon with interior re-entrant corner at (0,0)",
        boundary_conditions="Clamped root on top (y=1), shear traction on right (x=1)",
        expected_qoi_formula="Mode I singularity exponent lambda approx 0.54448 (Williams root); asymptotic energy defect O(h^(2*lambda)) ~ O(h^1.089)",
        expected_order_h=0.544,  # theoretical singularity exponent
        expected_tolerance="Strain energy strictly monotonic from below; energy increment reduction strictly monotonic; observed rate lambda_obs in [0.45, 0.75] < 1.0",
        limitations="Singular corner derivative; pre-asymptotic uniform meshes contain both singular corner and regular bulk energy components",
        cross_check_target="Williams Mode I analytical singularity; monotonic strain energy convergence and rate degradation",
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


# =============================================================================
# Authoritative Closed-Form Benchmark Reference Solutions
# =============================================================================

def lame_cylinder_analytical_plane_stress(
    r: np.ndarray,
    a: float,
    b: float,
    P_int: float,
    E: float,
    nu: float,
) -> Dict[str, np.ndarray]:
    """
    Authoritative closed-form solution for thick cylinder under internal pressure in Plane Stress.
    r: radial evaluation coordinates (a <= r <= b)
    Returns dictionary with radial displacement u_r, radial stress sigma_rr, and hoop stress sigma_tt.
    """
    r_arr = np.asarray(r, dtype=float)
    denom = E * (b**2 - a**2)
    u_r = (P_int * a**2 / denom) * ((1.0 - nu) * r_arr + (1.0 + nu) * b**2 / r_arr)
    s_rr = (P_int * a**2 / (b**2 - a**2)) * (1.0 - b**2 / r_arr**2)
    s_tt = (P_int * a**2 / (b**2 - a**2)) * (1.0 + b**2 / r_arr**2)
    s_zz = np.zeros_like(r_arr)
    return {"u_r": u_r, "sigma_rr": s_rr, "sigma_tt": s_tt, "sigma_zz": s_zz}


def lame_cylinder_analytical_plane_strain(
    r: np.ndarray,
    a: float,
    b: float,
    P_int: float,
    E: float,
    nu: float,
) -> Dict[str, np.ndarray]:
    """
    Authoritative closed-form solution for thick cylinder under internal pressure in Plane Strain.
    r: radial evaluation coordinates (a <= r <= b)
    Returns dictionary with radial displacement u_r, radial stress sigma_rr, hoop stress sigma_tt, and axial stress sigma_zz.
    """
    r_arr = np.asarray(r, dtype=float)
    denom = E * (b**2 - a**2)
    u_r = ((1.0 + nu) * P_int * a**2 / denom) * ((1.0 - 2.0 * nu) * r_arr + b**2 / r_arr)
    s_rr = (P_int * a**2 / (b**2 - a**2)) * (1.0 - b**2 / r_arr**2)
    s_tt = (P_int * a**2 / (b**2 - a**2)) * (1.0 + b**2 / r_arr**2)
    s_zz = (2.0 * nu * P_int * a**2 / (b**2 - a**2)) * np.ones_like(r_arr)
    return {"u_r": u_r, "sigma_rr": s_rr, "sigma_tt": s_tt, "sigma_zz": s_zz}


def kirsch_plate_hole_analytical(
    r: np.ndarray,
    theta: np.ndarray,
    a: float,
    sigma_inf: float,
) -> Dict[str, np.ndarray]:
    """
    Authoritative Kirsch solution for infinite plate with circular hole under uniaxial tension.
    r: radial distance from center of hole (r >= a)
    theta: angle from axis of far-field tension (radians)
    Returns sigma_rr, sigma_tt, sigma_rth, and peak stress concentration factor Kt = 3.0 at (r=a, theta=pi/2).
    """
    r_arr = np.asarray(r, dtype=float)
    th_arr = np.asarray(theta, dtype=float)
    a2_r2 = (a / r_arr) ** 2
    a4_r4 = a2_r2 ** 2

    s_rr = (sigma_inf / 2.0) * (1.0 - a2_r2) + (sigma_inf / 2.0) * (1.0 - 4.0 * a2_r2 + 3.0 * a4_r4) * np.cos(2.0 * th_arr)
    s_tt = (sigma_inf / 2.0) * (1.0 + a2_r2) - (sigma_inf / 2.0) * (1.0 + 3.0 * a4_r4) * np.cos(2.0 * th_arr)
    s_rth = -(sigma_inf / 2.0) * (1.0 + 2.0 * a2_r2 - 3.0 * a4_r4) * np.sin(2.0 * th_arr)

    return {"sigma_rr": s_rr, "sigma_tt": s_tt, "sigma_rth": s_rth, "Kt_exact": 3.0}
