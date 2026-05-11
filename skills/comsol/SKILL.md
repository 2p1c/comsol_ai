---
name: comsol
description: >
  General-purpose COMSOL Multiphysics automation via the mph Python library and
  COMSOL Java API. Use when the user needs to: (1) Create COMSOL models
  programmatically (geometry, materials, physics, multiphysics, mesh, probes),
  (2) Set up and run parametric/time-domain/frequency studies, (3) Extract and
  export simulation results (probe data, field evaluations, cut points),
  (4) Debug COMSOL API calls or model-tree navigation, (5) Work with .mph files
  from Python. Covers COMSOL versions 6.0–6.3 on Windows/Linux/macOS with mph
  stand-alone and client-server modes. All API patterns verified against
  COMSOL 6.2 via live testing. Self-improves by logging debugging discoveries
  to references/debugging-log.md.
compatibility: >
  Requires COMSOL Multiphysics 6.0–6.3, mph Python library, numpy, pandas.
  Stand-alone mode only on Windows. Linux/macOS require client-server mode.
metadata:
  version: "1.2.0"
  comsol_version: "6.2"
---

# COMSOL Automation via mph

Use the `mph` Python library to control COMSOL programmatically.
Always prefer the **Java API bridge** (`model.java`) over mph's Python wrapper
for physics/material/mesh/study/probe setup — the mph Python API is mainly for
parameters, geometry, saving, and solving.

## Quick-start checklist

1. `pip install mph numpy pandas`
2. `mph.option('session', 'stand-alone')` on Windows (fastest)
3. `client = mph.start(cores=N)` → `pymodel = client.create('Name')`
4. Access the Java bridge: `model = pymodel.java`
5. Build the model using the patterns below
6. Save: `pymodel.save('file.mph')`
7. Solve: `pymodel.solve()`
8. Extract data and export

## Essential API patterns (all discovered via live testing against COMSOL 6.2)

### Model structure — ALWAYS create the component explicitly

```python
model.modelNode().create("comp1")          # required BEFORE any geometry
model.geom().create("geom1", 3)            # 3D geometry
model.geom("geom1").feature().create("blk1", "Block")
model.geom("geom1").feature("blk1").set("size", ["Lx", "Ly", "Lz"])
model.geom("geom1").run("fin")
comp = model.component("comp1")            # now accessible
```

**Critical**: `model.component("comp1")` only works after `modelNode().create("comp1")`.
Do NOT mix mph Python geometry creation with Java API — choose one path and stick to it.

### Global parameters

```python
model.param().set("Lx", "40 [mm]")
model.param().set("T_amb", "293.15 [K]")
```

### Material properties — MUST use propertyGroup('def')

```python
mat = comp.material().create("mat1", "Common")
mat.label("My Material")
mat.selection().all()
grp = mat.propertyGroup("def")
grp.set("density",                   "2700 [kg/m^3]")
grp.set("youngsmodulus",             "69e9 [Pa]")
grp.set("poissonsratio",             "0.33")
grp.set("thermalconductivity",       "167 [W/(m*K)]")
grp.set("heatcapacity",              "896 [J/(kg*K)]")
grp.set("thermalexpansioncoefficient", "23.6e-6 [1/K]")
```

**Critical**: NEVER use `mat.set(prop, val)` — it will fail. ALWAYS go through
`mat.propertyGroup("def").set(prop, val)`.

### Physics interfaces — verified tags for COMSOL 6.2

| Desired physics | Correct Java tag | Via |
|---|---|---|
| Heat Transfer in Solids | `"HeatTransfer"` | `comp.physics().create("ht", "HeatTransfer", "geom1")` |
| Solid Mechanics | `"SolidMechanics"` | `comp.physics().create("solid", "SolidMechanics", "geom1")` |
| Thermal Expansion (multiphysics) | `"ThermalExpansion"` | `comp.multiphysics().create("te1", "ThermalExpansion", "geom1")` |

**Wrong tags that will FAIL**: `"HeatTransferInSolids"`, `"HeatTransferSolids"`,
`"StructuralMechanics"`, `"Solid"`.

### Boundary condition features — verified tags

| Feature | Tag | Dimension |
|---|---|---|
| Boundary heat source (laser) | `"BoundaryHeatSource"` | `2` (3D boundary) |
| Low-reflecting boundary | `"LowReflectingBoundary"` | `2` (3D boundary) |

**Wrong tags that will FAIL**: `"HeatFlux"`, `"InwardHeatFlux"`, `"AbsorbingBoundary"`.

### Selections — prefer direct entity numbers

Named selections via `feature.selection().set("name")` FAILS in client API.
Use `.named("name")` for mesh features or direct entity numbers for physics:

```python
# Physics features: direct entity numbers (MUST use jpype.JArray)
bhs.selection().set(jpype.JArray(jpype.JInt, 1)([6]))          # boundary 6 = top

# Mesh Size features: named selection via .named() (NOT .set())
size_fine.selection().named("sel_wave_region")

# Ball selection for mesh refinement (entitydim is STRING, radius is "r")
fine_sel = comp.selection().create("sel_wave_region", "Ball")
fine_sel.set("entitydim", "3")     # string "3", not int 3!
fine_sel.set("posx", "x0")
fine_sel.set("posy", "y0")
fine_sel.set("posz", "Lz/2")
fine_sel.set("r", "r_coarse")      # "r" not "radius"!
```

### Mesh — Size nodes and FreeTet

```python
mesh = comp.mesh().create("mesh1")
mesh.feature("size").set("hmax", "h_coarse")
mesh.feature("size").set("hmin", "0.01 [mm]")

# Local refinement (Ball selection, entitydim string, r not radius)
fine = mesh.feature().create("size_fine", "Size")
fine.set("hmax", "h_fine")
fine_sel = comp.selection().create("sel_fine", "Ball")
fine_sel.set("entitydim", "3")     # STRING!
fine_sel.set("posx", "x0")
fine_sel.set("posy", "y0")
fine_sel.set("posz", "Lz/2")
fine_sel.set("r", "r_coarse")      # "r" NOT "radius"!
fine.selection().named("sel_fine") # .named() NOT .set()!

mesh.feature().create("ftet1", "FreeTet")
mesh.run()
```

### Probes — DomainPointProbe unavailable in client API

`comp.probe().create(name, "DomainPointProbe")` throws "Operation cannot be
created in this context" in COMSOL 6.2 client mode. **Use CutPoint3D datasets
after solving instead:**

```python
res = model.result()
cp = res.dataset().create("cpt_0_0", "CutPoint3D")
cp.set("data", "dset1")                     # parent solution dataset
cp.set("pointx", str(x))
cp.set("pointy", str(y))
cp.set("pointz", str(z))
val = res.numerical("cpt_0_0", "w", "mm")   # evaluate displacement
```

### Time-dependent study

```python
study = model.study().create("std1")
step = study.feature().create("time", "Transient")
step.set("tlist", "range(0, 5e-9, 10e-6)")
step.set("rtol", "1e-5")
```

### Thermal Expansion coupling

```python
te = comp.multiphysics().create("te1", "ThermalExpansion", "geom1")
te.set("Tref", "T_amb")
try:
    tem = te.feature().create("tem1", "ThermalExpansionModel")
    tem.set("HeatTransferInterface", "ht")
    tem.set("StructuralInterface", "solid")
except Exception:
    pass
try:
    te.set("Temperature", "T")
except Exception:
    pass
```

## Solving: build–solve separation (comsolbatch)

mph stand-alone mode runs in a **headless JVM** (no Swing GUI). This means:
- `ModelUtil.showProgress()` → crash
- `SolverLog` feature → "cannot create in this context"
- Progress window → impossible

**Recommended architecture**: build with mph, solve with comsolbatch.

### Build phase (mph, always fast)

```bash
python laser_ultrasound_model.py --build-only
```

Creates `.mph` with all physics, mesh, and study settings. Inspect in COMSOL GUI.

### Solve phase (comsolbatch, real-time progress)

```python
import subprocess, pathlib

output_dir = pathlib.Path("output")
output_dir.mkdir(parents=True, exist_ok=True)

cmd = [
    r"C:\Program Files\COMSOL\COMSOL62\Multiphysics\bin\win64\comsolbatch.exe",
    "-inputfile",  str(pathlib.Path("laser_ultrasound_model.mph").resolve()),
    "-outputfile", str((output_dir / "solved_model.mph").resolve()),
    "-batchlog",   str((output_dir / "solver_progress.log").resolve()),
]

proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, bufsize=1, encoding="utf-8", errors="replace")
for line in proc.stdout:
    print(f"  {line.rstrip()}")     # real-time: Time-step N, Nonlinear its: M, ...
proc.wait()
```

Output looks like:
```
Time-step 1, Nonlinear iterations: 2, Convergence: 1.2e-6
Time-step 2, Nonlinear iterations: 1, Convergence: 8.3e-7
...
```

### Post-solve (mph, data extraction)

```python
client = mph.start(cores=4)
model = client.load(str(output_dir / "solved_model.mph"))
# Then use CutPoint3D / result().numerical() to extract data
```

### Alternative: solve in COMSOL Desktop GUI

Open the `.mph` in COMSOL Desktop → Study → Compute. Full progress window
with convergence plots, real-time probe graphs, and solver log.

## Common pitfalls & fallbacks

- `mph.start()` stand-alone fails → switch to `mph.option('session', 'client-server')`
- Physics tag unknown → check `references/api-reference.md` for verified tags
- `mat.set()` fails → MUST use `mat.propertyGroup("def").set(prop, val)`
- `model.component("comp1")` fails → `modelNode().create("comp1")` must be called first
- `set("entitydim", 2)` ambiguous → pass as string: `set("entitydim", "2")`
- `set("radius", ...)` unknown → use `"r"` not `"radius"`
- `selection().set("name")` → use `.named("name")` for named, `.set(JArray([N]))` for nums
- `BoxSelection` / `BallSelection` unknown → drop `Selection` suffix: `"Box"`, `"Ball"`
- `DomainPointProbe` fails → use `result().dataset().create("cpt", "CutPoint3D")` post-solve
- `selection().all()` on `free1` → Free BC is read-only, skip it
- Unicode in print → GBK console; use ASCII: `W/m^2`, `--`, `-`
- Solver fails → save .mph, open in COMSOL GUI, inspect setup
- Probe data missing → probes unavailable via client API; use CutPoint3D evaluation
- Progress window not showing → mph stand-alone is headless (no Swing). Use
  comsolbatch for text progress, or open .mph in COMSOL Desktop GUI
- SolverLog not creatable → same client-API limitation as probes. Use
  comsolbatch's `-batchlog` flag which writes progress to a file
- comsolbatch path errors → create output dir first, use absolute resolved paths
- ModelUtil.showProgress crashes → JVM has no Swing toolkit in stand-alone mode

## Self-improvement mechanism

After every debugging session where new COMSOL API behavior is discovered,
update `references/debugging-log.md` with:

1. The error symptom
2. The root cause
3. The working solution
4. COMSOL version

Also update `references/api-reference.md` if new tags are discovered or old ones
are found to be version-specific.

## Reference files

- `references/api-reference.md` — complete tag reference for physics, features, materials
- `references/laser-ultrasound.md` — worked example: laser-induced guided waves
- `references/debugging-log.md` — accumulated debugging experience
- `scripts/laser_ultrasound_model.py` — copy of the working simulation script
- `scripts/plot_results.py` — visualization script
