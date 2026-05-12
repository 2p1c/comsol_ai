# COMSOL Java API Tag Reference

Verified against COMSOL 6.2 + mph 1.3.1. Tags are case-sensitive.

## Physics interface tags

| Physics | Tag (`comp.physics().create(tag, type, geom)`) | Verified |
|---|---|---|
| Heat Transfer in Solids | `"HeatTransfer"` | 6.2 |
| Solid Mechanics | `"SolidMechanics"` | 6.2 |
| Electrostatics | `"Electrostatics"` | not tested |
| Pressure Acoustics | `"PressureAcoustics"` | not tested |
| Electric Currents | `"ElectricCurrents"` | not tested |
| Magnetic Fields | `"MagneticFields"` | not tested |
| Laminar Flow | `"LaminarFlow"` | not tested |

### Failed tags (do NOT use)

- `"HeatTransferInSolids"` — Unknown physics interface
- `"StructuralMechanics"` — Unknown physics interface
- `"Solid"` — Unknown physics interface
- `"HT"`, `"ht"`, `"solid"` — shorthand tags not valid as type strings

## Multiphysics coupling tags

| Coupling | Tag (`comp.multiphysics().create(tag, type, geom)`) | Verified |
|---|---|---|
| Thermal Expansion | `"ThermalExpansion"` | 6.2 (multiphysics node NOT configurable — use lemm1 sub-feature) |
| Thermal Stress | `"ThermalStress"` | 6.2 |
| Acoustic-Structure Boundary | `"AcousticStructureBoundary"` | not tested |

**Thermal Expansion — correct approach:**
```python
lemm = solid.feature("lemm1")                           # Linear Elastic Material
tef = lemm.feature().create("tef1", "ThermalExpansion")  # sub-feature, NOT multiphysics
tef.set("Tref", "T_amb")
tef.set("alpha", "23.6e-6 [1/K]")
```

## Material types

| Type | Tag | Notes |
|---|---|---|
| Common / generic | `"Common"` | Most flexible, set properties via `propertyGroup("def")` |
| Linear Elastic | `"LinearElastic"` | not tested |

## Material property names (on `propertyGroup("def")`)

| Property | Name for `set()` | Example |
|---|---|---|
| Density | `"density"` | `"2700 [kg/m^3]"` |
| Young's modulus | `"youngsmodulus"` | `"69e9 [Pa]"` |
| Poisson's ratio | `"poissonsratio"` | `"0.33"` |
| Thermal conductivity | `"thermalconductivity"` | `"167 [W/(m*K)]"` |
| Heat capacity | `"heatcapacity"` | `"896 [J/(kg*K)]"` |
| Thermal expansion coeff. | `"thermalexpansioncoefficient"` | `"23.6e-6 [1/K]"` |
| Electrical conductivity | `"electricalconductivity"` | not tested |
| Relative permittivity | `"relativepermittivity"` | not tested |

Note: properties seem to be case-insensitive (`"Density"` and `"density"` both work).

## Heat Transfer feature tags

| Feature | Tag | Dim | Purpose |
|---|---|---|---|
| Boundary Heat Source | `"BoundaryHeatSource"` | 2 | Laser / surface heating |
| Heat Source | `"HeatSource"` | 3 | Volumetric heating |
| Temperature | `"Temperature"` | 2 | Fixed temperature BC |
| Thermal Insulation | `"ThermalInsulation"` | 2 | Default, auto-created |
| Initial Values | `"init1"` | — | Auto-created |

### Failed Heat Transfer feature tags

- `"HeatFlux"` — does NOT exist as a feature tag (use `"BoundaryHeatSource"`)
- `"InwardHeatFlux"` — does NOT exist
- `"BoundaryHeatFlux"` — does NOT exist

## Solid Mechanics feature tags

| Feature | Tag | Dim | Purpose |
|---|---|---|---|
| Low-Reflecting Boundary | `"LowReflectingBoundary"` | 2 | Absorbing BC for waves |
| Fixed Constraint | `"FixedConstraint"` | 2 | Dirichlet BC |
| Boundary Load | `"BoundaryLoad"` | 2 | Applied force/traction |
| Free | `"Free"` | 2 | Default (auto-created) |
| Initial Values | `"init1"` | — | Auto-created |

## Selection types

**Critical**: COMSOL 6.2 selection type tags drop the `Selection` suffix.
Use `"Box"`, `"Ball"`, `"Explicit"`, `"Cylinder"`, `"Union"`, etc.
The longer forms (`"BoxSelection"`, `"BallSelection"`, `"ExplicitSelection"`) all FAIL.

| Type | Tag | Purpose |
|---|---|---|
| Box selection | `"Box"` | Select by coordinate condition |
| Ball selection | `"Ball"` | Select by distance from point |
| Explicit | `"Explicit"` | Select by entity numbers |
| Cylinder | `"Cylinder"` | Select by cylinder region |
| Union | `"Union"` | Combine selections |
| Intersection | `"Intersection"` | Intersect selections |
| Difference | `"Difference"` | Subtract selections |
| Adjacent | `"Adjacent"` | Select adjacent entities |

## Probe types

| Type | Tag | Purpose |
|---|---|---|
| Domain Point Probe | `"DomainPointProbe"` | Time series at a point |
| Boundary Probe | `"BoundaryProbe"` | not tested |
| Domain Probe | `"DomainProbe"` | not tested |

## Study types

| Study step | Tag | Purpose |
|---|---|---|
| Time Dependent | `"Transient"` | Time-domain |
| Stationary | `"Stationary"` | Steady-state |
| Frequency Domain | `"FrequencyDomain"` | not tested |
| Eigenfrequency | `"Eigenfrequency"` | not tested |

## General ModelClient methods

The `model.java` object is a `com.comsol.clientapi.impl.ModelClient`. Key methods:

| Method | Returns | Purpose |
|---|---|---|
| `modelNode()` | ModelNodeListClient | Root model tree |
| `component(tag)` | Component | Access component by tag |
| `geom(tag)` | Geometry | Access geometry |
| `material(tag)` | Material | Access material |
| `physics(tag)` | Physics | Access physics interface |
| `multiphysics(tag)` | Multiphysics | Access multiphysics |
| `mesh(tag)` | Mesh | Access mesh |
| `study()` | StudyList | Create/access studies |
| `result()` | Result | Access results/tables |
| `param()` | Parameters | Set global parameters |
| `func()` | Functions | Create functions |
| `selection()` | Selections | Create selections |
| `probe()` | Probes | Create probes |
| `sol(tag)` | Solution | Access solution |

## mph Python API (what it's good for)

| Operation | Code |
|---|---|
| Start COMSOL | `client = mph.start(cores=N)` |
| New model | `pymodel = client.create('Name')` |
| Save | `pymodel.save('path.mph')` |
| Solve | `pymodel.solve()` |
| Java bridge | `model = pymodel.java` |
| Set parameter | `pymodel.parameter('name', 'value [unit]')` |

## Units

Always include units in brackets: `"40 [mm]"`, `"69e9 [Pa]"`, `"293.15 [K]"`.
The default length unit is mm, default temperature unit is K.

## Client API limitations (verified against COMSOL 6.2)

### Functions that evaluate to 0 via the client API

| Expression | Works? | Note |
|---|---|---|
| `exp(-r²/D)` with D > 5e-5 | YES | exp argument < 40 everywhere |
| `exp(-r²/D)` with D ≤ 1e-5 | NO | Underflow at far nodes → global zero |
| `max(a, b)` on boundary | NO | Evaluates to 0 |
| `min(a, b)` on boundary | NO | Evaluates to 0 |
| `if(cond, a, b)` on boundary | NO | Evaluates to 0 |
| `(x > val1) * (x < val2)` on boundary | NO | Spatial comparisons → 0 |
| `(t > val1) * (t < val2)` | YES | Temporal comparisons work |

### Nodes/features that throw "Operation cannot be created"

- `DomainPointProbe` — use `pymodel.evaluate()` + nearest-node instead
- `SolverLog` — unavailable; use COMSOL Desktop for progress monitoring
- `ThermalExpansionModel` (sub-feature of multiphysics node) — use `lemm1` sub-feature instead

### Other limitations

- `res.numerical()` only accepts 0–1 string arguments (the tag of a NumericalFeature)
- `pymodel.save()` fails if filename was used earlier in the same session — use UUID suffix
- `comsolbatch` does not save solution datasets to the output .mph
