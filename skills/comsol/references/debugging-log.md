# Debugging Log — COMSOL + mph

Self-improvement log. Append new entries after each debugging session.
Format: symptom → root cause → solution.

---

## Entry 1 — 2026-05-11: Initial API discovery
- **COMSOL**: 6.2, **mph**: 1.3.1, **OS**: Windows 11

### `model.component("comp1")` → Unknown model
- **Root cause**: Used mph Python API `model.create("geometries/...")` which creates
  components in mph's own layer, not in the Java model tree. The Java API can't find them.
- **Solution**: Create component explicitly via Java API first:
  `model.java.modelNode().create("comp1")`. Do NOT mix mph Python geometry calls
  with Java API calls.

### `mat.set("youngsmodulus", ...)` → Unknown property
- **Root cause**: COMSOL's `Common` material type stores properties inside
  a property group named `"def"`, not on the material node itself.
- **Solution**: Use `mat.propertyGroup("def").set("youngsmodulus", value)`.

### `comp.physics().create("ht", "HeatTransferInSolids", "geom1")` → Unknown physics interface
- **Root cause**: The tag is `"HeatTransfer"`, not `"HeatTransferInSolids"`.
- **Solution**: Use `"HeatTransfer"` for heat transfer, `"SolidMechanics"` for solid mechanics.

### `ht.feature().create("hf1", "HeatFlux", 2)` → failed
- **Root cause**: The boundary heat flux feature is called `"BoundaryHeatSource"`,
  not `"HeatFlux"`.
- **Solution**: Use `BoundaryHeatSource` with `dim=2` for 3D surface heating.

### `mph.discovery.discover()` → no attribute
- **Root cause**: mph 1.3.1 doesn't have this method; the auto-discovery is
  built into `mph.start()`.
- **Solution**: Just call `mph.start()` — it auto-discovers COMSOL via registry
  (Windows), default paths, or `comsol` command in PATH.

### `mph.option('session', 'stand-alone')` won't work on Linux/macOS
- **Root cause**: Stand-alone mode uses Windows-specific JVM embedding.
- **Solution**: On non-Windows, always use `mph.option('session', 'client-server')`.

### Chinese/garbled characters in mph.tree() output
- **Root cause**: mph displays labels in the OS locale. On Chinese Windows,
  COMSOL's built-in node labels appear as Chinese characters.
- **Solution**: Ignore — it's cosmetic. Use tags (not labels) for API calls.

### `java.modelNode().getNChildren()` → AttributeError
- **Root cause**: `ModelNodeListClient` doesn't have `getNChildren()`. It's a
  different object type than the standard COMSOL API `ModelNode`.
- **Solution**: Use `java.modelNode().tags()` to get child tags.

---

## Entry 2 — 2026-05-11: Material property discovery
- **COMSOL**: 6.2, **mph**: 1.3.1

### Finding correct material property names
- **Method**: Iterated through `mat.propertyGroup("def")` methods and tried
  `getAllowedPropertyValues()` for each candidate property name.
- **Result**: Lowercase names work: `density`, `youngsmodulus`, `poissonsratio`,
  `thermalconductivity`, `heatcapacity`, `thermalexpansioncoefficient`.
  Case-insensitive (`Density` also works, as does `YoungsModulus`).
- **Short names also valid**: `rho`, `E`, `nu`, `k`, `Cp`, `alpha` all showed
  as valid properties via `getAllowedPropertyValues()`.

---

## Entry 3 — 2026-05-11: Selection type tags
- **COMSOL**: 6.2, **mph**: 1.3.1, **OS**: Windows 11

### `comp.selection().create("sel_top", "BoxSelection")` → Unknown selection type
- **Root cause**: COMSOL 6.2 selection type tags drop the `Selection` suffix.
- **Solution**: Use `"Box"`, `"Ball"`, `"Explicit"`, `"Cylinder"`, `"Union"`,
  `"Intersection"`, `"Difference"`, `"Adjacent"`.
- **All failed tags**: `"BoxSelection"`, `"BallSelection"`, `"ExplicitSelection"`,
  `"CylinderSelection"`, `"UnionSelection"`, `"IntersectionSelection"`,
  `"DifferenceSelection"`, `"AdjacentSelection"`.

---

## Entry 4 — 2026-05-11: entitydim type + selection API details
- **COMSOL**: 6.2, **mph**: 1.3.1, **OS**: Windows 11

### `set("entitydim", 2)` → Ambiguous overloads
- **Root cause**: JPype can't disambiguate `set(String, int)` vs `set(String, boolean)`.
- **Solution**: Pass entitydim as string: `set("entitydim", "2")`.

### Box `condition` is not a coordinate filter
- **Root cause**: Box selection's `condition` property is an entity inclusion type
  ("intersects", "inside", "somevertex", "allvertices"), not a coordinate expression.
- **Solution**: Use `zmin`/`zmax` for coordinate bounds on Box selections.

### Ball `radius` → Unknown property
- **Root cause**: The radius property is named `"r"`, not `"radius"`.
- **Solution**: Use `set("r", value)` for Ball selections.

## Entry 5 — 2026-05-11: Named selection application
- **COMSOL**: 6.2, **mph**: 1.3.1

### `feature.selection().set("sel_name")` → No matching overloads
- **Root cause**: `SelectionClient.set()` expects `int[]` (entity numbers),
  not a string. Named selections use a different method.
- **Solution**: Use `feature.selection().named("sel_name")` for named selections.
  Use `feature.selection().set(JArray(JInt)([6]))` for direct entity numbers.

### `solid.feature("free1").selection().all()` → Selection is not editable
- **Root cause**: The `Free` BC is the default — its selection is auto-managed.
- **Solution**: Skip setting selection on `free1` (it applies to all boundaries
  by default, overridden only where other BCs are applied).

## Entry 6 — 2026-05-11: DomainPointProbe not available
- **COMSOL**: 6.2, **mph**: 1.3.1

### `comp.probe().create(name, "DomainPointProbe")` → Operation cannot be created
- **Root cause**: `DomainPointProbe` is not available through the COMSOL client
  API in version 6.2. All probe types tested and failed.
- **Solution**: Use `model.result().dataset().create(name, "CutPoint3D")`
  after solving instead. Evaluate via `res.numerical(tag, expr, unit)`.

## Entry 7 — 2026-05-11: Unicode in print strings
- **COMSOL**: 6.2, **OS**: Windows 11 (GBK locale)

### `UnicodeEncodeError: 'gbk' codec can't encode character`
- **Root cause**: Chinese Windows consoles default to GBK encoding. Unicode
  characters like `m²`, `—` (em dash), `─` (box drawing) fail to print.
- **Solution**: Use ASCII-only in print strings: `W/m^2`, `--`, `-`.

---

## Entry 8 — 2026-05-11: SolverLog + progress window both unavailable
- **COMSOL**: 6.2, **mph**: 1.3.1, **OS**: Windows 11

### `study.feature().create("solLog", "SolverLog")` → Operation cannot be created
- **Root cause**: `SolverLog` (and all log feature variants) are not available
  through the COMSOL client API, same limitation as `DomainPointProbe`.
- **Solution**: Use `comsolbatch` external process for solving. It outputs
  real-time text progress (time steps, iterations, convergence) to stdout.

### `ModelUtil.showProgress(true)` → crash (No toolkit factory 'swing')
- **Root cause**: mph's stand-alone mode embeds COMSOL in a headless JVM
  without Swing GUI toolkit. Progress window is impossible in this mode.
- **Solution**: Two options:
  1. Build with mph `--build-only`, then solve via `comsolbatch` (text progress)
  2. Open .mph in COMSOL Desktop GUI and solve there (full GUI progress)

### `comsolbatch` output directory must exist before running
- **Root cause**: comsolbatch does not create parent directories for
  `-outputfile` or `-batchlog`.
- **Solution**: Create output directory (`Path.mkdir(parents=True)`) before
  invoking comsolbatch. Use absolute resolved paths to avoid encoding issues.

---

## Entry 9 — 2026-05-12: `exp()` underflow causes expression to evaluate to 0 globally
- **COMSOL**: 6.2, **mph**: 1.3.1, **OS**: Windows 11

### Gaussian heat source `Q0 * exp(-r²/(2*sigma_s²))` → zero heating
- **Root cause**: COMSOL client API evaluates `exp(-large_argument)` at all boundary
  nodes. When `exp()` underflows to exactly 0 at far corners (e.g. r_max²/D > ~40),
  COMSOL sets the ENTIRE expression to 0 globally, not just at those nodes.
- **Verification**: Binary search found the threshold at denominator D ≈ 1e-5.
  `exp(-r²/0.1)` works (D=0.1 > 1e-5). `exp(-r²/1e-5)` fails (D=1e-5).
  For a 20mm plate corner (r=14mm), need D > r²/40 ≈ 5e-5.
- **Solution**: Use `sigma_s ≥ 5mm` (D = 2*sigma_s² ≥ 5e-5). This ensures
  exp argument < 40 everywhere → no underflow → expression evaluates correctly.
  Alternatively, use a polynomial cap `1 - r²/(2*sigma_s²)` without clamping.
- **Note**: `max()`, `min()`, `if()`, and spatial comparisons like
  `((x-x0)² < 2*sigma_s²)` ALSO fail via the client API (evaluate to 0),
  making it impossible to clamp spatial expressions.

## Entry 10 — 2026-05-12: ThermalExpansion coupling not working
- **COMSOL**: 6.2, **mph**: 1.3.1

### `comp.multiphysics().create("te1","ThermalExpansion")` → no displacement
- **Root cause**: The `ThermalExpansionModel` sub-feature cannot be created via
  the client API (`Unknown feature ID`). Without it, the coupling between
  HeatTransfer and SolidMechanics is inactive.
- **Solution**: Add `ThermalExpansion` as a sub-feature of the **Linear Elastic
  Material** node instead:
  ```python
  lemm = solid.feature("lemm1")
  tef = lemm.feature().create("tef1", "ThermalExpansion")
  tef.set("Tref", "T_amb")
  tef.set("alpha", "23.6e-6 [1/K]")
  ```
  This applies thermal expansion directly within the constitutive law, bypassing
  the multiphysics coupling node entirely.

## Entry 11 — 2026-05-12: CutPoint3D + res.numerical() not working
- **COMSOL**: 6.2, **mph**: 1.3.1

### `res.numerical("cpt","w","mm")` → TypeError (no matching overloads)
- **Root cause**: `ResultsClient.numerical()` only accepts 0 or 1 string argument
  (the tag of a NumericalFeature), not expression/unit arguments.
- **Solution**: Use `pymodel.evaluate("w","mm")` which returns a
  (n_timesteps, n_nodes) NumPy array. Find nearest mesh nodes to target
  coordinates using `pymodel.evaluate("x","mm")` at t=0, then extract
  time series from those node indices.

## Entry 12 — 2026-05-12: File lock on model save
- **COMSOL**: 6.2, **mph**: 1.3.1

### `pymodel.save("name.mph")` → File locked by another model
- **Root cause**: mph client caches file associations. Saving to a filename
  previously used in the same session fails.
- **Solution**: Save pre-solve backups with a unique name (UUID suffix):
  `f"_pre_solve_{uuid.uuid4().hex[:8]}.mph"`. The final solved model can
  be saved via the unique path returned by comsolbatch or mph.

---

## Template for new entries

```markdown
## Entry N — YYYY-MM-DD: short description
- **COMSOL**: X.Y, **mph**: X.Y.Z, **OS**: [Windows/Linux/macOS]

### Symptom
- **Root cause**:
- **Solution**:
```
