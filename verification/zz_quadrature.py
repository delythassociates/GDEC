"""
verification/zz_quadrature.py
Independent Exact-Quadrature Zienkiewicz-Zhu (ZZ) Operator Implementation.

Mathematical formulation:
For each triangular element K:
    eta_{K, op}^2 = t * int_K (sigma^* - sigma_h)^T * D^{-1} * (sigma^* - sigma_h) dOmega

where:
- sigma^* is the recovered continuous stress field, interpolated linearly across K
  from recovered nodal stress values via P1 shape functions:
      sigma^*(x, y) = N_0(x, y) * sigma^*_0 + N_1(x, y) * sigma^*_1 + N_2(x, y) * sigma^*_2
- sigma_h is the piecewise constant (P0) finite element stress on K.
- (sigma^* - sigma_h) is therefore an affine (degree <= 1) vector polynomial on K.
- The quadratic energy integrand:
      q(x, y) = (sigma^*(x, y) - sigma_h)^T * D^{-1} * (sigma^*(x, y) - sigma_h)
  is a polynomial of degree <= 2 in (x, y).

Quadrature Rule:
The 3-point edge-midpoint quadrature rule on triangles has algebraic precision of degree 2:
- Integration points:
    m_{01} = 0.5 * (v_0 + v_1)  (barycentric coordinates: (0.5, 0.5, 0.0))
    m_{12} = 0.5 * (v_1 + v_2)  (barycentric coordinates: (0.0, 0.5, 0.5))
    m_{20} = 0.5 * (v_2 + v_0)  (barycentric coordinates: (0.5, 0.0, 0.5))
- Weights:
    w_1 = w_2 = w_3 = (1/3) * Area(K)

Because q(x, y) is quadratic, this 3-point midpoint rule integrates q(x, y) EXACTLY
with zero polynomial truncation error.

Clean-room independence:
- Does NOT call the production estimator's centroid integration routine.
- Does NOT use the production centroid result.
- Explicitly implements constitutive compliance matrix D^{-1}.
- Includes built-in unit tests verifying exact integration on quadratic polynomials.
"""

from __future__ import annotations
from typing import Dict, Tuple, Any
import numpy as np


def verify_midpoint_quadrature_precision() -> float:
    """
    Unit test verifying exact integration of a known quadratic polynomial
    over the standard reference triangle T_ref with vertices (0,0), (1,0), (0,1).
    Polynomial: f(x, y) = 3*x^2 + 2*x*y + 5*y^2 + 4*x - y + 7
    Analytical integral:
        int_0^1 int_0^{1-x} f(x, y) dy dx = 4.75
    Returns maximum absolute error (should be < 1e-15).
    """
    v0 = np.array([0.0, 0.0])
    v1 = np.array([1.0, 0.0])
    v2 = np.array([0.0, 1.0])
    area = 0.5

    # 3 edge midpoints
    m01 = 0.5 * (v0 + v1)
    m12 = 0.5 * (v1 + v2)
    m20 = 0.5 * (v2 + v0)
    quad_points = [m01, m12, m20]
    weight = area / 3.0

    def f(x, y):
        return 3.0 * x**2 + 2.0 * x * y + 5.0 * y**2 + 4.0 * x - y + 7.0

    num_integral = sum(weight * f(p[0], p[1]) for p in quad_points)
    exact_integral = 4.75
    return float(abs(num_integral - exact_integral))


def compute_independent_exact_zz_operator(
    points: np.ndarray,
    triangles: np.ndarray,
    element_areas: np.ndarray,
    element_stresses: np.ndarray,
    compliance_3x3: np.ndarray,
    thickness: float = 1.0,
) -> Dict[str, Any]:
    """
    Computes:
    1. eta_{K, op}: exact-quadrature energy norm error indicator per element.
    2. eta_{K, L2}: plain-L2 stress difference indicator per element (diagnostic).
    3. eta_{K, impl}: centroid approximation indicator per element (for comparison).

    Returns dictionary with per-element arrays and total norms.
    """
    nelements = triangles.shape[1]
    nnodes = points.shape[1]

    # Step 1: Recover continuous nodal stresses via area-weighted averaging (SPR)
    nodal_stresses_sum = np.zeros((3, nnodes), dtype=float)
    nodal_weights_sum = np.zeros(nnodes, dtype=float)

    for local_v in range(3):
        nodes = triangles[local_v, :]
        for comp in range(3):
            np.add.at(nodal_stresses_sum[comp], nodes, element_areas * element_stresses[comp])
        np.add.at(nodal_weights_sum, nodes, element_areas)

    nodal_recovered = nodal_stresses_sum / np.maximum(nodal_weights_sum[None, :], 1e-14)

    # Step 2: Nodal recovered stresses on each triangle
    v0 = triangles[0, :]
    v1 = triangles[1, :]
    v2 = triangles[2, :]

    sig_n0 = nodal_recovered[:, v0]
    sig_n1 = nodal_recovered[:, v1]
    sig_n2 = nodal_recovered[:, v2]

    # Step 3: Exact 3-point midpoint quadrature evaluation
    # Shape functions at edge midpoints:
    # m01: N = [0.5, 0.5, 0.0]
    # m12: N = [0.0, 0.5, 0.5]
    # m20: N = [0.5, 0.0, 0.5]
    sig_m01 = 0.5 * (sig_n0 + sig_n1)
    sig_m12 = 0.5 * (sig_n1 + sig_n2)
    sig_m20 = 0.5 * (sig_n2 + sig_n0)

    # Stress difference Delta sigma = sigma^* - sigma_h at the 3 midpoints
    d_m01 = sig_m01 - element_stresses
    d_m12 = sig_m12 - element_stresses
    d_m20 = sig_m20 - element_stresses

    # Quadratic energy integrand q = d^T * D^{-1} * d
    C_inv = compliance_3x3
    q_01 = np.sum(d_m01 * (C_inv @ d_m01), axis=0)
    q_12 = np.sum(d_m12 * (C_inv @ d_m12), axis=0)
    q_20 = np.sum(d_m20 * (C_inv @ d_m20), axis=0)

    # Exact integral over triangle: sum(weight * q) where weight = Area / 3
    eta_sq_op = (thickness * element_areas / 3.0) * (q_01 + q_12 + q_20)
    eta_sq_op = np.maximum(eta_sq_op, 0.0)
    eta_op = np.sqrt(eta_sq_op)
    total_energy_error_op = float(np.sqrt(np.sum(eta_sq_op)))

    # Step 4: Plain L2 diagnostic (unweighted by compliance)
    l2_01 = np.sum(d_m01**2, axis=0)
    l2_12 = np.sum(d_m12**2, axis=0)
    l2_20 = np.sum(d_m20**2, axis=0)
    eta_sq_l2 = (thickness * element_areas / 3.0) * (l2_01 + l2_12 + l2_20)
    total_l2_stress_error = float(np.sqrt(np.sum(eta_sq_l2)))

    # Step 5: Production implementation centroid evaluation (for exact R_ratio comparison)
    sig_centroid = (sig_n0 + sig_n1 + sig_n2) / 3.0
    d_centroid = sig_centroid - element_stresses
    q_centroid = np.sum(d_centroid * (C_inv @ d_centroid), axis=0)
    eta_sq_impl = thickness * element_areas * q_centroid
    eta_sq_impl = np.maximum(eta_sq_impl, 0.0)
    total_energy_error_impl = float(np.sqrt(np.sum(eta_sq_impl)))

    return {
        "eta_op_per_element": eta_op,
        "total_energy_error_op": total_energy_error_op,
        "total_energy_error_impl": total_energy_error_impl,
        "total_l2_stress_error": total_l2_stress_error,
        "ratio_impl_to_op": float(total_energy_error_impl / total_energy_error_op),
    }
