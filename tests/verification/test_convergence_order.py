"""
Rigorous mesh-convergence and observed-order verification tests.
Implements mathematically justified convergence testing:
1. Optimal convergence rates for smooth solutions in H1 (order ~1.0) and L2 (order ~2.0).
2. Degraded convergence rates for re-entrant corner singularities (order ~1.33 in L2 for 3pi/2 corner).
Uses log-log linear regression with R^2 goodness-of-fit validation.
"""
from __future__ import annotations

import math
from typing import List, Tuple
import numpy as np
import pytest
import skfem
from skfem.models.poisson import laplace


def fit_convergence_rate(h_values: List[float], errors: List[float]) -> Tuple[float, float, float]:
    """
    Fit convergence order p in error = C * h^p via linear regression in log-log space.
    Returns (p, C, r_squared).
    """
    assert len(h_values) == len(errors) and len(h_values) >= 3
    log_h = np.log(np.array(h_values))
    log_e = np.log(np.array(errors))

    # Linear fit: log(e) = p * log(h) + log(C)
    coeffs = np.polyfit(log_h, log_e, 1)
    p = float(coeffs[0])
    c = float(np.exp(coeffs[1]))

    # Compute coefficient of determination R^2
    y_pred = np.polyval(coeffs, log_h)
    ss_res = float(np.sum((log_e - y_pred) ** 2))
    ss_tot = float(np.sum((log_e - np.mean(log_e)) ** 2))
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 1.0

    return p, c, r_squared


class TestMeshConvergenceAndObservedOrder:
    """Rigorous verification of observed convergence rates against mathematical theory."""

    def test_smooth_mms_convergence_l2_and_h1(self):
        """
        Verify that smooth MMS Poisson problem achieves optimal theoretical rates:
        - L2 error order in [1.85, 2.15] (theoretical O(h^2))
        - H1 error order in [0.85, 1.15] (theoretical O(h^1))
        - Goodness-of-fit R^2 >= 0.99
        """
        h_vals = []
        l2_errors = []
        h1_errors = []

        # Mesh hierarchy: h = 1/4, 1/8, 1/16, 1/32
        for N in [4, 8, 16, 32]:
            mesh = skfem.MeshTri.init_tensor(np.linspace(0, 1, N + 1), np.linspace(0, 1, N + 1))
            basis = skfem.Basis(mesh, skfem.ElementTriP1())
            K = skfem.asm(laplace, basis)

            @skfem.LinearForm
            def rhs(v, w):
                x, y = w.x[0], w.x[1]
                return 2.0 * np.pi**2 * np.sin(np.pi * x) * np.sin(np.pi * y) * v

            f = skfem.asm(rhs, basis)
            D = mesh.boundary_nodes()
            u = skfem.solve(*skfem.condense(K, f, D=D))

            @skfem.Functional
            def l2_err_form(w):
                x, y = w.x[0], w.x[1]
                u_ex = np.sin(np.pi * x) * np.sin(np.pi * y)
                return (w['u'] - u_ex)**2

            @skfem.Functional
            def h1_err_form(w):
                x, y = w.x[0], w.x[1]
                du_dx = np.pi * np.cos(np.pi * x) * np.sin(np.pi * y)
                du_dy = np.pi * np.sin(np.pi * x) * np.cos(np.pi * y)
                grad_fem = w['u'].grad
                return (grad_fem[0] - du_dx)**2 + (grad_fem[1] - du_dy)**2

            l2_e = np.sqrt(skfem.asm(l2_err_form, basis, u=basis.interpolate(u)))
            h1_e = np.sqrt(skfem.asm(h1_err_form, basis, u=basis.interpolate(u)))

            h_vals.append(1.0 / N)
            l2_errors.append(l2_e)
            h1_errors.append(h1_e)

        p_l2, c_l2, r2_l2 = fit_convergence_rate(h_vals, l2_errors)
        p_h1, c_h1, r2_h1 = fit_convergence_rate(h_vals, h1_errors)

        # Assert mathematically grounded bounds
        assert 1.85 <= p_l2 <= 2.15, f"Smooth MMS L2 order {p_l2:.3f} outside [1.85, 2.15]"
        assert 0.85 <= p_h1 <= 1.15, f"Smooth MMS H1 order {p_h1:.3f} outside [0.85, 1.15]"
        assert r2_l2 >= 0.99, f"L2 log-log linearity R^2 {r2_l2:.4f} < 0.99"
        assert r2_h1 >= 0.99, f"H1 log-log linearity R^2 {r2_h1:.4f} < 0.99"

    def test_reentrant_corner_singularity_rate_degradation(self):
        """
        Verify that a re-entrant corner singularity (3pi/2 angle) exhibits degraded rate:
        - L2 observed order is bounded in [1.20, 1.45], asymptotically matching 2*alpha = 4/3 ~ 1.333
        - The rate is strictly degraded compared to the smooth problem (p_l2 < 1.60 vs ~ 2.0).
        """
        def u_exact(x, y):
            theta = np.arctan2(y, x)
            # Quadrants 2, 3, 4: map angle from [pi/2, 2*pi] to [0, 3*pi/2]
            phi = np.where(theta >= np.pi / 2, theta - np.pi / 2, theta + 3 * np.pi / 2)
            r = np.sqrt(x**2 + y**2)
            return r**(2.0 / 3.0) * np.sin((2.0 / 3.0) * phi)

        @skfem.Functional
        def l2_err_form(w):
            x, y = w.x[0], w.x[1]
            return (w['u'] - u_exact(x, y))**2

        h_vals, errors = [], []
        for k in [1, 2, 3, 4]:
            m = skfem.MeshTri.init_lshaped().refined(k)
            basis = skfem.Basis(m, skfem.ElementTriP1())
            K = skfem.asm(laplace, basis)
            D = m.boundary_nodes()

            u_dir = np.zeros(basis.N)
            u_dir[D] = u_exact(m.p[0, D], m.p[1, D])

            u = skfem.solve(*skfem.condense(K, np.zeros(basis.N), x=u_dir, D=D))
            err = np.sqrt(skfem.asm(l2_err_form, basis, u=basis.interpolate(u)))

            h_vals.append(1.0 / (2**k))
            errors.append(err)

        p_sing, _, r2_sing = fit_convergence_rate(h_vals, errors)

        # Theoretical L2 rate for alpha = 2/3 corner singularity is 2*alpha = 4/3 ~ 1.333
        assert 1.20 <= p_sing <= 1.45, f"Singular L2 order {p_sing:.3f} outside [1.20, 1.45]"
        assert p_sing < 1.60, f"Singular order {p_sing:.3f} should be strictly degraded from 2.0"
        assert r2_sing >= 0.98, f"Singular log-log fit R^2 {r2_sing:.4f} < 0.98"

    def test_fit_convergence_rate_edge_cases(self):
        """Verify error handling and mathematical validation in fit_convergence_rate."""
        with pytest.raises(AssertionError):
            fit_convergence_rate([1.0, 0.5], [0.1, 0.05])  # Requires >= 3 points

        with pytest.raises(AssertionError):
            fit_convergence_rate([1.0, 0.5, 0.25], [0.1, 0.05])  # Mismatched lengths

        # Exact quadratic decay: e = 0.5 * h^2
        h = [0.5, 0.25, 0.125, 0.0625]
        e = [0.5 * x**2 for x in h]
        p, c, r2 = fit_convergence_rate(h, e)
        assert p == pytest.approx(2.0, abs=1e-8)
        assert c == pytest.approx(0.5, abs=1e-8)
        assert r2 == pytest.approx(1.0, abs=1e-8)
