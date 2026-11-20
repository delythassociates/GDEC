"""
Phase C-P Pilot Benchmarks: Singular and Smooth Elasticity Solutions.
Implements:
1. Case A: Williams Mode-I Re-entrant Corner Eigenfunction (traction-free corner notch, zero body force).
2. Case B: Weakly-Singular Manufactured Solution with symbolic body force derivation.
3. High-order quadrature verification for singular integrands.
4. Problem Analyser refusal for singular point stress QoIs.
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np
import scipy.sparse.linalg as spla
import skfem as fem
from skfem import Basis, ElementVector, ElementTriP1, FacetBasis

from gdec.fem.elasticity import ConstitutiveTensor, LinearElasticitySolver


# --- Case A: Williams Mode-I Corner Eigenfunction ---
LAMBDA_WILLIAMS = 0.544483736782464
OMEGA_WILLIAMS = 1.5 * np.pi
ALPHA_WILLIAMS = OMEGA_WILLIAMS / 2.0  # 3*pi/4
Q_WILLIAMS = float(np.cos((LAMBDA_WILLIAMS - 1.0) * ALPHA_WILLIAMS) / np.cos((LAMBDA_WILLIAMS + 1.0) * ALPHA_WILLIAMS))


def williams_displacement_field(
    x: np.ndarray, y: np.ndarray, E: float = 100e9, nu: float = 0.30
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Exact Mode-I Williams re-entrant corner displacement field.
    Corner is at (0, 0), notch occupies x >= 0, y <= 0 (fourth quadrant).
    Traction-free on theta = 0 and theta = 3*pi/2.
    """
    mu = E / (2.0 * (1.0 + nu))
    kappa = 3.0 - 4.0 * nu  # plane strain
    lam = LAMBDA_WILLIAMS
    Q = Q_WILLIAMS

    r = np.sqrt(x**2 + y**2)
    # Avoid zero division at singularity
    r_safe = np.maximum(r, 1e-15)

    theta = np.arctan2(y, x)
    theta = np.where(theta < 0, theta + 2.0 * np.pi, theta)
    phi = theta - ALPHA_WILLIAMS

    ur = (r_safe**lam / (2.0 * mu)) * (
        (kappa - Q * (lam + 1.0)) * np.cos(lam * phi) - lam * np.cos((lam - 2.0) * phi)
    )
    uphi = (r_safe**lam / (2.0 * mu)) * (
        (kappa + Q * (lam + 1.0)) * np.sin(lam * phi) + lam * np.sin((lam - 2.0) * phi)
    )

    ux = ur * np.cos(theta) - uphi * np.sin(theta)
    uy = ur * np.sin(theta) + uphi * np.cos(theta)

    # Singularity at origin has zero displacement
    zero_mask = r < 1e-14
    ux = np.where(zero_mask, 0.0, ux)
    uy = np.where(zero_mask, 0.0, uy)

    return ux, uy


def create_l_shaped_mesh(n: int = 4) -> fem.MeshTri:
    r"""
    Create structured L-shaped mesh in [-1, 1]^2 \ ([0, 1] x [-1, 0]).
    Re-entrant corner is at (0, 0).
    """
    m1 = fem.MeshTri.init_tensor(np.linspace(-1.0, 0.0, n + 1), np.linspace(-1.0, 0.0, n + 1))
    m2 = fem.MeshTri.init_tensor(np.linspace(-1.0, 0.0, n + 1), np.linspace(0.0, 1.0, n + 1))
    m3 = fem.MeshTri.init_tensor(np.linspace(0.0, 1.0, n + 1), np.linspace(0.0, 1.0, n + 1))
    mesh = (m1 + m2 + m3).remove_duplicate_nodes().oriented()
    return mesh


# --- Case B: Weakly-Singular Manufactured Solution ---
def case_b_displacement_field(x: np.ndarray, y: np.ndarray, alpha: float = 1.40) -> Tuple[np.ndarray, np.ndarray]:
    """Displacement u_x = x^alpha, u_y = y^alpha on [0, 1]^2."""
    x_safe = np.maximum(x, 0.0)
    y_safe = np.maximum(y, 0.0)
    ux = x_safe**alpha
    uy = y_safe**alpha
    return ux, uy


def case_b_body_force(x: np.ndarray, y: np.ndarray, c: ConstitutiveTensor, alpha: float = 1.40) -> Tuple[np.ndarray, np.ndarray]:
    """
    Symbolically derived body force f = -div(sigma) for u_x = x^alpha, u_y = y^alpha.
    sigma_xx = c11 * alpha * x^(alpha-1) + c12 * alpha * y^(alpha-1)
    sigma_yy = c12 * alpha * x^(alpha-1) + c11 * alpha * y^(alpha-1)
    sigma_xy = 0
    f_x = - d(sigma_xx)/dx = -c11 * alpha * (alpha - 1) * x^(alpha - 2)
    f_y = - d(sigma_yy)/dy = -c11 * alpha * (alpha - 1) * y^(alpha - 2)
    """
    x_safe = np.maximum(x, 1e-12)
    y_safe = np.maximum(y, 1e-12)
    coeff = -c.c11 * alpha * (alpha - 1.0)
    fx = coeff * (x_safe ** (alpha - 2.0))
    fy = coeff * (y_safe ** (alpha - 2.0))
    return fx, fy
