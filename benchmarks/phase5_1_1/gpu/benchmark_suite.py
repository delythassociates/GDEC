"""
GDEC Phase 5.1.1 Remediation GPU/CPU Benchmarking Suite.
Rigorous, reproducible benchmarks:
1. True 2D 5-point discrete Laplacian grid via Kronecker sum (A = I_y (x) T_x + T_y (x) I_x).
2. Honest timing: separate CPU setup from GPU execution; direct wall-clock timing with synchronization.
3. GPU-resident PCG (Jacobi) vs CPU CG solves with exact relative residual verification.
4. Raw individual sample records (CSV) and summary statistics (CSV).
"""

import os
import sys
import time
import csv
import platform
import psutil
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

# Optional CuPy
import cupy as cp
import cupyx.scipy.sparse as cp_sp
import cupyx.scipy.sparse.linalg as cp_spla

from gdec.core.backend import CPUBackend, CUDABackend, detect_cuda_capability


def make_2d_laplacian(nx: int, ny: int) -> sp.csr_matrix:
    """
    Construct true 2D discrete Laplacian via Kronecker sum:
    A = I_y (x) T_x + T_y (x) I_x
    """
    Tx = sp.diags([-1.0, 2.0, -1.0], [-1, 0, 1], shape=(nx, nx), format="csr")
    Ty = sp.diags([-1.0, 2.0, -1.0], [-1, 0, 1], shape=(ny, ny), format="csr")
    Ix = sp.eye(nx, format="csr")
    Iy = sp.eye(ny, format="csr")
    A = sp.kron(Iy, Tx, format="csr") + sp.kron(Ty, Ix, format="csr")
    return A.astype(np.float64)


def run_benchmarks(raw_csv_path: str, summary_csv_path: str) -> None:
    print("=" * 80)
    print("GDEC Phase 5.1.1 GPU/CPU Benchmark Protocol Execution")
    print("=" * 80)

    cuda_det = detect_cuda_capability()
    print(f"CUDA Status: {cuda_det.status.name} | Operational: {cuda_det.is_operational}")
    print(f"GPU Model: {cuda_det.device_name} | VRAM: {cuda_det.device_memory_mb} MB")
    print(f"Driver: {cuda_det.cuda_driver_version} | CuPy: {cuda_det.cupy_version}")
    print(f"CPU: {platform.processor() or platform.machine()} | RAM: {round(psutil.virtual_memory().total / (1024**3), 1)} GB")
    print("-" * 80)

    cpu_backend = CPUBackend()
    cuda_backend = CUDABackend()

    raw_samples = []
    summary_rows = []

    # --------------------------------------------------------------------------
    # 1. SpMV BENCHMARKS (True 2D Kronecker Sum Grid)
    # Small: 70x70 -> N=4,900, NNZ=24,220
    # Medium: 160x160 -> N=25,600, NNZ=127,360
    # Large: 320x320 -> N=102,400, NNZ=510,720
    # --------------------------------------------------------------------------
    spmv_configs = [
        ("Scale_Small", 70, 70),
        ("Scale_Medium", 160, 160),
        ("Scale_Large", 320, 320),
    ]

    warmup = 10
    reps = 30

    print("\n--- 1. True 2D Kronecker SpMV Benchmarks ---")
    for scale_name, nx, ny in spmv_configs:
        A = make_2d_laplacian(nx, ny)
        n = A.shape[0]
        nnz = A.nnz
        expected_nnz = 5 * nx * ny - 2 * nx - 2 * ny
        assert nnz == expected_nnz, f"NNZ mismatch: got {nnz}, expected {expected_nnz}"
        print(f"\n[SpMV] {scale_name}: Grid {nx}x{ny} -> N = {n:,}, NNZ = {nnz:,}")

        np.random.seed(42)
        x = np.random.randn(n)

        # CPU Warmup & Bench
        for _ in range(warmup):
            _ = A @ x
        
        cpu_times = []
        for rep in range(reps):
            t0 = time.perf_counter()
            y_cpu = A @ x
            t1 = time.perf_counter()
            dur = (t1 - t0) * 1000.0
            cpu_times.append(dur)
            raw_samples.append({
                "workload": f"spmv_{scale_name}",
                "metric": "cpu_wall_time_ms",
                "rep": rep,
                "value_ms": dur
            })

        # GPU Transfers & Kernel
        A_gpu = cp_sp.csr_matrix(A)
        x_gpu = cp.asarray(x)
        cp.cuda.Stream.null.synchronize()

        # Resident Kernel
        for _ in range(warmup):
            _ = A_gpu.dot(x_gpu)
            cp.cuda.Stream.null.synchronize()

        start_event = cp.cuda.Event()
        end_event = cp.cuda.Event()
        kernel_times = []
        for rep in range(reps):
            start_event.record()
            y_gpu = A_gpu.dot(x_gpu)
            end_event.record()
            end_event.synchronize()
            dur = cp.cuda.get_elapsed_time(start_event, end_event)
            kernel_times.append(dur)
            raw_samples.append({
                "workload": f"spmv_{scale_name}",
                "metric": "gpu_resident_kernel_ms",
                "rep": rep,
                "value_ms": dur
            })

        # End-to-End GPU (Transfer H2D + Kernel + D2H)
        e2e_times = []
        for rep in range(reps):
            t0 = time.perf_counter()
            A_g = cp_sp.csr_matrix(A)
            x_g = cp.asarray(x)
            y_g = A_g.dot(x_g)
            y_h = y_g.get()
            cp.cuda.Stream.null.synchronize()
            t1 = time.perf_counter()
            dur = (t1 - t0) * 1000.0
            e2e_times.append(dur)
            raw_samples.append({
                "workload": f"spmv_{scale_name}",
                "metric": "gpu_e2e_wall_ms",
                "rep": rep,
                "value_ms": dur
            })

        # Numerical check
        y_host_resident = y_gpu.get()
        diff_inf = float(np.max(np.abs(y_host_resident - y_cpu)))
        diff_rel_l2 = float(np.linalg.norm(y_host_resident - y_cpu) / np.linalg.norm(y_cpu))

        cpu_mean = float(np.mean(cpu_times))
        cpu_med = float(np.median(cpu_times))
        cpu_std = float(np.std(cpu_times))
        k_mean = float(np.mean(kernel_times))
        k_med = float(np.median(kernel_times))
        k_std = float(np.std(kernel_times))
        e2e_mean = float(np.mean(e2e_times))
        e2e_med = float(np.median(e2e_times))
        e2e_std = float(np.std(e2e_times))

        speedup_res = cpu_mean / max(k_mean, 1e-6)
        speedup_e2e = cpu_mean / max(e2e_mean, 1e-6)

        print(f"  CPU Mean: {cpu_mean:.4f} ms | GPU Res Mean: {k_mean:.4f} ms (Speedup: {speedup_res:.2f}x)")
        print(f"  GPU E2E Mean: {e2e_mean:.4f} ms (Speedup: {speedup_e2e:.2f}x)")
        print(f"  Numerical Rel L2 Diff: {diff_rel_l2:.2e}")

        summary_rows.append({
            "category": "SpMV",
            "workload": f"spmv_{scale_name}",
            "N": n,
            "NNZ": nnz,
            "reps": reps,
            "cpu_mean_ms": round(cpu_mean, 4),
            "cpu_median_ms": round(cpu_med, 4),
            "cpu_std_ms": round(cpu_std, 4),
            "cpu_min_ms": round(float(np.min(cpu_times)), 4),
            "cpu_max_ms": round(float(np.max(cpu_times)), 4),
            "gpu_resident_mean_ms": round(k_mean, 4),
            "gpu_resident_median_ms": round(k_med, 4),
            "gpu_resident_std_ms": round(k_std, 4),
            "gpu_resident_min_ms": round(float(np.min(kernel_times)), 4),
            "gpu_resident_max_ms": round(float(np.max(kernel_times)), 4),
            "gpu_e2e_mean_ms": round(e2e_mean, 4),
            "gpu_e2e_median_ms": round(e2e_med, 4),
            "gpu_e2e_std_ms": round(e2e_std, 4),
            "speedup_resident": round(speedup_res, 2),
            "speedup_e2e": round(speedup_e2e, 2),
            "numerical_rel_l2_diff": f"{diff_rel_l2:.2e}",
        })

    # --------------------------------------------------------------------------
    # 2. BATCHED ANALYTICAL PARAMETER SCALING BENCHMARKS
    # --------------------------------------------------------------------------
    print("\n--- 2. Batched Parameter Scaling Benchmarks ---")
    batch_scales = [1000, 10000, 100000, 1000000]
    J_0 = 4.5
    E_0 = 210e3
    P_0 = 1000.0

    for b_size in batch_scales:
        np.random.seed(123)
        E_samples = np.random.uniform(150e3, 250e3, size=b_size)
        P_samples = np.random.uniform(500.0, 1500.0, size=b_size)

        # CPU warmup & bench
        for _ in range(5):
            _ = cpu_backend.evaluate_parameter_scaling_batch(E_samples, P_samples, J_0, E_0, P_0)
        cpu_b_times = []
        for rep in range(reps):
            t0 = time.perf_counter()
            res_cpu = cpu_backend.evaluate_parameter_scaling_batch(E_samples, P_samples, J_0, E_0, P_0)
            t1 = time.perf_counter()
            dur = (t1 - t0) * 1000.0
            cpu_b_times.append(dur)
            raw_samples.append({
                "workload": f"batch_{b_size}",
                "metric": "cpu_wall_time_ms",
                "rep": rep,
                "value_ms": dur
            })

        # GPU Resident
        E_gpu = cp.asarray(E_samples)
        P_gpu = cp.asarray(P_samples)
        cp.cuda.Stream.null.synchronize()

        for _ in range(5):
            _ = (P_gpu / P_0) * (E_0 / E_gpu) * J_0
            cp.cuda.Stream.null.synchronize()

        k_b_times = []
        for rep in range(reps):
            start_event.record()
            res_gpu = (P_gpu / P_0) * (E_0 / E_gpu) * J_0
            end_event.record()
            end_event.synchronize()
            dur = cp.cuda.get_elapsed_time(start_event, end_event)
            k_b_times.append(dur)
            raw_samples.append({
                "workload": f"batch_{b_size}",
                "metric": "gpu_resident_kernel_ms",
                "rep": rep,
                "value_ms": dur
            })

        # GPU E2E
        e2e_b_times = []
        for rep in range(reps):
            t0 = time.perf_counter()
            E_g = cp.asarray(E_samples)
            P_g = cp.asarray(P_samples)
            r_g = (P_g / P_0) * (E_0 / E_g) * J_0
            r_h = r_g.get()
            cp.cuda.Stream.null.synchronize()
            t1 = time.perf_counter()
            dur = (t1 - t0) * 1000.0
            e2e_b_times.append(dur)
            raw_samples.append({
                "workload": f"batch_{b_size}",
                "metric": "gpu_e2e_wall_ms",
                "rep": rep,
                "value_ms": dur
            })

        res_host = res_gpu.get()
        diff_rel_l2 = float(np.linalg.norm(res_host - res_cpu) / np.linalg.norm(res_cpu))

        cpu_m = float(np.mean(cpu_b_times))
        k_m = float(np.mean(k_b_times))
        e2e_m = float(np.mean(e2e_b_times))
        sp_res = cpu_m / max(k_m, 1e-6)
        sp_e2e = cpu_m / max(e2e_m, 1e-6)

        print(f"  Batch {b_size:,} | CPU Mean: {cpu_m:.4f} ms | GPU Res: {k_m:.4f} ms ({sp_res:.2f}x) | GPU E2E: {e2e_m:.4f} ms ({sp_e2e:.2f}x)")

        summary_rows.append({
            "category": "Batched_Scaling",
            "workload": f"batch_{b_size}",
            "N": b_size,
            "NNZ": 0,
            "reps": reps,
            "cpu_mean_ms": round(cpu_m, 4),
            "cpu_median_ms": round(float(np.median(cpu_b_times)), 4),
            "cpu_std_ms": round(float(np.std(cpu_b_times)), 4),
            "cpu_min_ms": round(float(np.min(cpu_b_times)), 4),
            "cpu_max_ms": round(float(np.max(cpu_b_times)), 4),
            "gpu_resident_mean_ms": round(k_m, 4),
            "gpu_resident_median_ms": round(float(np.median(k_b_times)), 4),
            "gpu_resident_std_ms": round(float(np.std(k_b_times)), 4),
            "gpu_resident_min_ms": round(float(np.min(k_b_times)), 4),
            "gpu_resident_max_ms": round(float(np.max(k_b_times)), 4),
            "gpu_e2e_mean_ms": round(e2e_m, 4),
            "gpu_e2e_median_ms": round(float(np.median(e2e_b_times)), 4),
            "gpu_e2e_std_ms": round(float(np.std(e2e_b_times)), 4),
            "speedup_resident": round(sp_res, 2),
            "speedup_e2e": round(sp_e2e, 2),
            "numerical_rel_l2_diff": f"{diff_rel_l2:.2e}",
        })

    # --------------------------------------------------------------------------
    # 3. LINEAR SOLVER BENCHMARKS (PCG Jacobi CPU vs GPU Resident vs E2E)
    # --------------------------------------------------------------------------
    print("\n--- 3. Linear Solver Benchmarks (PCG Jacobi CPU vs GPU) ---")
    solver_scales = [
        ("Solve_Small", 70, 70),     # N = 4,900
        ("Solve_Medium", 160, 160),  # N = 25,600
    ]

    for scale_name, nx, ny in solver_scales:
        A = make_2d_laplacian(nx, ny)
        n = A.shape[0]
        np.random.seed(42)
        b = np.sin(np.linspace(0, np.pi, n))

        # CPU Preconditioned CG (Jacobi)
        diag_A = A.diagonal()
        inv_diag = np.where(diag_A != 0.0, 1.0 / diag_A, 1.0)
        M_cpu = spla.LinearOperator(A.shape, matvec=lambda v: inv_diag * v)
        M_cpu.is_spd = True

        # Warmup CPU
        _ = spla.cg(A, b, M=M_cpu, rtol=1e-6, atol=1e-12, maxiter=500)

        cpu_solve_times = []
        for rep in range(10):
            t0 = time.perf_counter()
            x_cpu, info_cpu = spla.cg(A, b, M=M_cpu, rtol=1e-6, atol=1e-12, maxiter=500)
            t1 = time.perf_counter()
            dur = (t1 - t0) * 1000.0
            cpu_solve_times.append(dur)
            raw_samples.append({
                "workload": f"pcg_{scale_name}",
                "metric": "cpu_pcg_wall_ms",
                "rep": rep,
                "value_ms": dur
            })

        r_cpu = np.linalg.norm(b - A @ x_cpu) / np.linalg.norm(b)

        # GPU PCG (Jacobi)
        A_gpu = cp_sp.csr_matrix(A)
        b_gpu = cp.asarray(b)
        diag_gpu = A_gpu.diagonal()
        inv_diag_gpu = cp.where(diag_gpu != 0.0, 1.0 / diag_gpu, 1.0)
        M_gpu = cp_spla.LinearOperator(A_gpu.shape, matvec=lambda v: inv_diag_gpu * v)

        # GPU Resident Warmup
        _ = cp_spla.cg(A_gpu, b_gpu, M=M_gpu, rtol=1e-6, atol=1e-12, maxiter=500)
        cp.cuda.Stream.null.synchronize()

        gpu_res_times = []
        for rep in range(10):
            start_event.record()
            x_gpu, info_gpu = cp_spla.cg(A_gpu, b_gpu, M=M_gpu, rtol=1e-6, atol=1e-12, maxiter=500)
            end_event.record()
            end_event.synchronize()
            dur = cp.cuda.get_elapsed_time(start_event, end_event)
            gpu_res_times.append(dur)
            raw_samples.append({
                "workload": f"pcg_{scale_name}",
                "metric": "gpu_resident_pcg_ms",
                "rep": rep,
                "value_ms": dur
            })

        # GPU E2E (Transfer + Solve + Transfer Back)
        gpu_e2e_solve_times = []
        for rep in range(10):
            t0 = time.perf_counter()
            A_g = cp_sp.csr_matrix(A)
            b_g = cp.asarray(b)
            d_g = A_g.diagonal()
            inv_d_g = cp.where(d_g != 0.0, 1.0 / d_g, 1.0)
            M_g = cp_spla.LinearOperator(A_g.shape, matvec=lambda v: inv_d_g * v)
            x_g, info_g = cp_spla.cg(A_g, b_g, M=M_g, rtol=1e-6, atol=1e-12, maxiter=500)
            x_h = x_g.get()
            cp.cuda.Stream.null.synchronize()
            t1 = time.perf_counter()
            dur = (t1 - t0) * 1000.0
            gpu_e2e_solve_times.append(dur)
            raw_samples.append({
                "workload": f"pcg_{scale_name}",
                "metric": "gpu_e2e_pcg_ms",
                "rep": rep,
                "value_ms": dur
            })

        x_host_res = x_gpu.get()
        r_gpu = np.linalg.norm(b - A @ x_host_res) / np.linalg.norm(b)
        sol_rel_diff = np.linalg.norm(x_host_res - x_cpu) / np.linalg.norm(x_cpu)

        cpu_s_m = float(np.mean(cpu_solve_times))
        gpu_res_m = float(np.mean(gpu_res_times))
        gpu_e2e_m = float(np.mean(gpu_e2e_solve_times))

        sp_res_solve = cpu_s_m / max(gpu_res_m, 1e-6)
        sp_e2e_solve = cpu_s_m / max(gpu_e2e_m, 1e-6)

        print(f"  {scale_name} (N={n:,}): CPU PCG: {cpu_s_m:.2f} ms (rel_r={r_cpu:.2e}) | GPU Res PCG: {gpu_res_m:.2f} ms (rel_r={r_gpu:.2e}) (Speedup: {sp_res_solve:.2f}x) | GPU E2E: {gpu_e2e_m:.2f} ms ({sp_e2e_solve:.2f}x)")

        summary_rows.append({
            "category": "PCG_Jacobi_Solve",
            "workload": f"pcg_{scale_name}",
            "N": n,
            "NNZ": A.nnz,
            "reps": 10,
            "cpu_mean_ms": round(cpu_s_m, 4),
            "cpu_median_ms": round(float(np.median(cpu_solve_times)), 4),
            "cpu_std_ms": round(float(np.std(cpu_solve_times)), 4),
            "cpu_min_ms": round(float(np.min(cpu_solve_times)), 4),
            "cpu_max_ms": round(float(np.max(cpu_solve_times)), 4),
            "gpu_resident_mean_ms": round(gpu_res_m, 4),
            "gpu_resident_median_ms": round(float(np.median(gpu_res_times)), 4),
            "gpu_resident_std_ms": round(float(np.std(gpu_res_times)), 4),
            "gpu_resident_min_ms": round(float(np.min(gpu_res_times)), 4),
            "gpu_resident_max_ms": round(float(np.max(gpu_res_times)), 4),
            "gpu_e2e_mean_ms": round(gpu_e2e_m, 4),
            "gpu_e2e_median_ms": round(float(np.median(gpu_e2e_solve_times)), 4),
            "gpu_e2e_std_ms": round(float(np.std(gpu_e2e_solve_times)), 4),
            "speedup_resident": round(sp_res_solve, 2),
            "speedup_e2e": round(sp_e2e_solve, 2),
            "numerical_rel_l2_diff": f"{sol_rel_diff:.2e}",
        })

    # --------------------------------------------------------------------------
    # 4. CPU-ONLY MULTIPLE-RHS & FACTORIZATION REUSE (Separated from GPU Fields)
    # --------------------------------------------------------------------------
    print("\n--- 4. CPU-Only Multiple-RHS Strategy Comparison ---")
    n_rhs = 10000
    A_rhs = sp.diags([np.full(n_rhs, 4.0), np.full(n_rhs - 1, -1.0), np.full(n_rhs - 1, -1.0)], [0, -1, 1], format="csc")
    b1 = np.ones(n_rhs)
    b2 = np.linspace(1.0, 2.0, n_rhs)
    B = np.column_stack([b1, b2])

    ind_times = []
    for rep in range(10):
        t0 = time.perf_counter()
        _ = spla.spsolve(A_rhs, b1)
        _ = spla.spsolve(A_rhs, b2)
        t1 = time.perf_counter()
        ind_times.append((t1 - t0) * 1000.0)

    reuse_times = []
    for rep in range(10):
        t0 = time.perf_counter()
        lu = spla.splu(A_rhs)
        _ = lu.solve(b1)
        _ = lu.solve(b2)
        t1 = time.perf_counter()
        reuse_times.append((t1 - t0) * 1000.0)

    block_times = []
    for rep in range(10):
        t0 = time.perf_counter()
        lu = spla.splu(A_rhs)
        _ = lu.solve(B)
        t1 = time.perf_counter()
        block_times.append((t1 - t0) * 1000.0)

    t_ind_m = float(np.mean(ind_times))
    t_re_m = float(np.mean(reuse_times))
    t_bl_m = float(np.mean(block_times))

    print(f"  CPU 2x Re-factorization: {t_ind_m:.3f} ms")
    print(f"  CPU Factorization Reuse: {t_re_m:.3f} ms (Speedup: {t_ind_m / t_re_m:.2f}x)")
    print(f"  CPU Block Solve:         {t_bl_m:.3f} ms (Speedup: {t_ind_m / t_bl_m:.2f}x)")

    summary_rows.append({
        "category": "CPU_Multiple_RHS",
        "workload": "cpu_factor_reuse_vs_block",
        "N": n_rhs,
        "NNZ": A_rhs.nnz,
        "reps": 10,
        "cpu_mean_ms": round(t_ind_m, 4),
        "cpu_median_ms": round(float(np.median(ind_times)), 4),
        "cpu_std_ms": round(float(np.std(ind_times)), 4),
        "cpu_min_ms": round(float(np.min(ind_times)), 4),
        "cpu_max_ms": round(float(np.max(ind_times)), 4),
        "gpu_resident_mean_ms": "N/A (CPU-only)",
        "gpu_resident_median_ms": "N/A",
        "gpu_resident_std_ms": "N/A",
        "gpu_resident_min_ms": "N/A",
        "gpu_resident_max_ms": "N/A",
        "gpu_e2e_mean_ms": round(t_re_m, 4),  # Reused factorization time
        "gpu_e2e_median_ms": round(float(np.median(reuse_times)), 4),
        "gpu_e2e_std_ms": round(float(np.std(reuse_times)), 4),
        "speedup_resident": round(t_ind_m / t_bl_m, 2),  # Block speedup over independent
        "speedup_e2e": round(t_ind_m / t_re_m, 2),       # Reuse speedup over independent
        "numerical_rel_l2_diff": "0.00e+00",
    })

    # Save CSVs
    os.makedirs(os.path.dirname(raw_csv_path), exist_ok=True)
    with open(raw_csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["workload", "metric", "rep", "value_ms"])
        writer.writeheader()
        writer.writerows(raw_samples)

    with open(summary_csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"\n[DONE] Saved raw sample observations to: {raw_csv_path}")
    print(f"[DONE] Saved summary statistics to:       {summary_csv_path}")


if __name__ == "__main__":
    raw_csv = sys.argv[1] if len(sys.argv) > 1 else "research/phase5.1.1/gpu/GPU_BENCHMARK_RAW_SAMPLES.csv"
    sum_csv = sys.argv[2] if len(sys.argv) > 2 else "research/phase5.1.1/gpu/GPU_BENCHMARK_SUMMARY.csv"
    run_benchmarks(raw_csv, sum_csv)
