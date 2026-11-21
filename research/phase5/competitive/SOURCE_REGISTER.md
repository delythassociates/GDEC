# GDEC Competitive Research Source and Citation Register

**Document Reference:** `research/phase5/competitive/SOURCE_REGISTER.md`  
**Workstream:** Agent 3 — Competitive and Market Capability Research  
**Target Release Context:** GDEC Phase 5.0 Parallel Engineering Research Programme  
**Status:** Complete — Sources Verified  

---

## 1. Primary Technical Sources & Documentation

### 1.1 Commercial Software Technical References
1. **ANSYS Inc.:**
   - *ANSYS Mechanical APDL Theory Reference*, Release 2024 R2, ANSYS Inc., Canonsburg, PA (2024). Details on sparse solver algorithms, GPU acceleration, and error norms.
   - *ANSYS Discovery: Real-Time Simulation and Modeling Guide*, ANSYS Inc. (2024). Level-0 interactive GPU voxel physics vs. Level-1 Mechanical solver mapping.
   - *ANSYS optiSLang: Methodology and Algorithms Guide*, Dynardo GmbH / ANSYS Inc. (2024). Metamodeling, polynomial chaos, multi-fidelity Kriging, and sensitivity analysis.
   - *ANSYS SimAI Technical Whitepaper: Deep Learning for Real-Time Physics*, ANSYS Inc. (2023). Geometric deep learning on surface meshes.
2. **Altair Engineering Inc.:**
   - *Altair OptiStruct 2024 User Guide and Theory*, Altair Engineering, Troy, MI (2024). Topology optimization, GPU-accelerated iterative solvers, and frequency response.
   - *Altair HyperStudy 2024 User Guide*, Altair Engineering (2024). Multi-disciplinary optimization, DOE sampling, and reliability assessment.
   - *Altair physicsAI: Fast Physics Predictions Using Machine Learning*, Altair Whitepaper (2023).
3. **Dassault Systèmes / SIMULIA:**
   - *Abaqus 2024 Theory Guide and Analysis User's Guide*, Dassault Systèmes, Vélizy-Villacoublay, France (2024). Sparse direct solver, iterative Krylov solvers, level-scheduling GPU acceleration, and error indicators.
   - *SIMULIA Isight 2024 Component Guide*, Dassault Systèmes (2024). Workflow orchestration and design optimization.
4. **Siemens Digital Industries Software:**
   - *Simcenter 3D Engineering Documentation*, Siemens PLM Software (2024). Simcenter Nastran structural solvers, GPU acceleration, and adaptive mesh remeshing.
   - *Simcenter HEEDS: Design Space Exploration Technical Overview*, Siemens (2024). SHERPA proprietary multi-search hybrid optimization.
5. **SimScale GmbH:**
   - *SimScale CAE Platform API and Solver Architecture Documentation*, Munich, Germany (2024). Cloud scheduling, remote parallel meshing, and open-source FEA/CFD orchestration.

### 1.2 Engineering Verification & Credibility Standards
1. **ASME V&V 10-2019:** *Standard for Verification and Validation in Computational Solid Mechanics*, American Society of Mechanical Engineers, New York (2019). Formal frameworks for code verification, discretization error estimation, and validation uncertainty comparison.
2. **ASME V&V 40-2018:** *Assessing Credibility of Computational Models through Verification and Validation: Application to Medical Devices*, ASME (2018). Risk-informed decision framework linking model credibility requirements to consequence of failure.
3. **NASA-STD-7009B:** *Standard for Models and Simulations*, National Aeronautics and Space Administration, Washington, DC (2021). Verification, validation, and uncertainty quantification (VV&UQ) reporting rules for decision support.
4. **Roache, P. J.:** *Verification and Validation in Computational Science and Engineering*, Hermosa Publishers, Albuquerque, NM (1998). Grid Convergence Index (GCI) and Richardson extrapolation.
5. **Celik, I. B., et al.:** "Procedure for Estimation and Reporting of Uncertainty Due to Discretization in CFD Applications," *Journal of Fluids Engineering*, 130(7), 078001 (2008). Unequal grid refinement ratio formulations.
