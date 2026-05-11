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

## Template for new entries

```markdown
## Entry N — YYYY-MM-DD: short description
- **COMSOL**: X.Y, **mph**: X.Y.Z, **OS**: [Windows/Linux/macOS]

### Symptom
- **Root cause**:
- **Solution**:
```
