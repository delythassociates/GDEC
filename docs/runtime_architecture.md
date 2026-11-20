# GDEC Runtime Architecture & Execution Control

## 1. Execution Workflow

The intelligent runtime manages the execution lifecycle:

```mermaid
sequenceDiagram
    participant User as CLI / Studio
    participant Planner as ExecutionPlanner
    participant Runtime as GDECRuntime
    participant Engine as FEM Engine
    participant Cost as CostModel

    User->>Planner: create_plan(ProblemIR)
    Planner-->>User: ExecutionPlan (initial grid, rationales)
    User->>Runtime: execute(plan, ir)
    loop Iterative Adaptation
        Runtime->>Engine: assemble_and_solve_primal(mesh)
        Engine-->>Runtime: u, reaction_forces
        Runtime->>Engine: assemble_and_solve_adjoint(mesh)
        Engine-->>Runtime: z
        Runtime->>Engine: evaluate_qoi_and_indicators(u, z)
        Engine-->>Runtime: QoI, element_indicators
        Runtime->>Runtime: check_convergence_criteria()
        alt Target Satisfied or Max Iterations Reached
            Runtime-->>User: Return ExecutionTrace (Converged)
        else Needs Refinement
            Runtime->>Cost: predict_refinement_dofs(marked_elements)
            Cost-->>Runtime: predicted_dofs
            Runtime->>Runtime: check_budget(predicted_dofs)
            Runtime->>Engine: refine_candidate_mesh(marked)
            Engine-->>Runtime: candidate_mesh
            Runtime->>Runtime: verify_actual_dofs(candidate_mesh)
            alt Exceeds Budget
                Runtime->>Runtime: rollback_mesh() & terminate
            else Within Budget
                Runtime->>Runtime: commit_mesh()
            end
        end
    end
```

## 2. Safe Refinement Transaction Protocol

To guarantee that computational budgets are never exceeded:
1. **Pre-solve Validation**: Before executing iteration 1, the initial mesh DOFs ($N_{\text{initial}}$) are verified against $N_{\text{budget}}$. If $N_{\text{initial}} > N_{\text{budget}}$, the computation aborts immediately.
2. **Predictive Check**: The cost model estimates $\hat{N}_{k+1}$. If $\hat{N}_{k+1} > N_{\text{budget}}$, refinement is throttled or terminated.
3. **Transactional Commit/Rollback**: Mesh refinement produces a tentative candidate mesh. If the candidate mesh exceeds $N_{\text{budget}}$, the candidate is discarded, the committed mesh is retained, and the simulation terminates cleanly with `stop_reason = "Refinement halted: Next mesh would exceed DOF budget"`.

## 3. Convergence Criterion
To prevent premature termination from accidental single-step error cancellations, GDEC requires that the relative successive change satisfies the tolerance for **two consecutive iterations**:
$$\Delta J_k = \frac{|J_k - J_{k-1}|}{|J_k|} \times 100\% \le \text{target\_percent}$$
