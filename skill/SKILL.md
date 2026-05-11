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
  stand-alone and client-server modes. This skill captures API lessons learned
  through live testing against COMSOL 6.2 and self-improves by logging new
  debugging discoveries.
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

### Selections — use BoxSelection with conditions

```python
top_sel = comp.selection().create("sel_top", "BoxSelection")
top_sel.set("entitydim", 2)
top_sel.set("condition", "z > Lz - 0.01[mm]")

feature.selection().set("sel_top")   # apply selection to a feature
```

### Mesh — Size nodes and FreeTet

```python
mesh = comp.mesh().create("mesh1")
mesh.feature("size").set("hmax", "h_coarse")
mesh.feature("size").set("hmin", "0.01 [mm]")

# Local refinement
fine = mesh.feature().create("size_fine", "Size")
fine.set("hmax", "h_fine")
fine_sel = comp.selection().create("sel_fine", "BallSelection")
fine_sel.set("entitydim", 3)
fine_sel.set("posx", "x0")
fine_sel.set("posy", "y0")
fine_sel.set("posz", "Lz/2")
fine_sel.set("radius", "r_coarse")
fine.selection().set("sel_fine")

mesh.feature().create("ftet1", "FreeTet")
mesh.run()
```

### Domain point probes

```python
probe = comp.probe().create("pdp_0_0", "DomainPointProbe")
probe.set("points", [x, y, z])
probe.set("expr", "w")   # z-displacement in Solid Mechanics
```

### Time-dependent study

```python
study = model.study().create("std1")
step = study.feature().create("time", "Transient")
step.set("tlist", "range(0, 5e-9, 10e-6)")
step.set("rtol", "1e-5")
```

### Data extraction from probes

```python
tbl = model.result().table("pdp_0_0")
raw = tbl.getReal()   # returns double[][] — [timestep][0] for single-expr probes
vals = [row[0] for row in raw]
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

## Fallbacks when things fail

- If `mph.start()` fails stand-alone → switch to `mph.option('session', 'client-server')`
- If physics tag fails → check `references/api-reference.md` for the full tag table
- If material `set()` fails → ensure you're using `propertyGroup("def").set()`
- If `model.component("comp1")` fails → ensure `modelNode().create("comp1")` was called first
- If solver fails → save .mph, open in COMSOL GUI, inspect setup manually

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
- `assets/laser_ultrasound_model.py` — copy of the working simulation script
- `assets/plot_results.py` — visualization script
