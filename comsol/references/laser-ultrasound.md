# Laser-Ultrasound Simulation Example

Worked example: 1064 nm pulsed laser → 2 mm aluminum plate → guided waves → array export.

## Physics summary

```
Laser pulse (Gaussian, 10 ns)
  ↓  BoundaryHeatSource on top surface
Heat Transfer in Solids (ht)
  ↓  ThermalExpansion (te1): T → thermal strain
Solid Mechanics (solid)
  ↓  Elastic waves propagate as Lamb waves
Domain Point Probes (7×7 grid)
  ↓  Record z-displacement w(t)
Export .npz + .csv
```

## Key parameter formulas

- Spatial sigma: `σ_s = w0 / 2` (for 1/e² radius w0)
- Temporal sigma: `σ_t = FWHM / (2√(2·ln2))` ≈ FWHM / 2.355
- Peak heat flux: `Q0 = E_abs / ((2π)^(3/2) · σ_s² · σ_t)`

## Laser heat source expression

```
Q0 * exp(-((x-x0)^2 + (y-y0)^2) / (2*sigma_s^2))
   * exp(-(t-t0)^2 / (2*sigma_t^2))
```

Applied as `Qb` property of a `BoundaryHeatSource` (dim=2) on the top surface.

## Verification checklist

After building the model (--build-only), open the .mph in COMSOL GUI and check:

1. **Geometry**: Block dimensions correct (40×40×2 mm)
2. **Material**: Aluminum 6061 assigned to all domains
3. **Heat Transfer**: BoundaryHeatSource on top surface with correct expression
4. **Solid Mechanics**: Free BC on all boundaries, LowReflectingBoundary on sides
5. **Thermal Expansion**: Coupling between ht and solid, Tref = T_amb
6. **Mesh**: Fine mesh (0.3 mm) in central region, coarser (1.5 mm) outside
7. **Probes**: Domain Point Probes at grid points, recording displacement w
8. **Study**: Time Dependent, range(0, 5e-9, 10e-6), rtol=1e-5

## Expected wave speeds (for validation)

| Mode | Approximate velocity |
|---|---|
| S0 (symmetric) | ~5400 m/s (low freq) |
| A0 (antisymmetric) | ~3000 m/s (low freq) at 2 MHz·mm |

At 20 mm from source:
- S0 arrival ≈ 3.7 μs
- A0 arrival ≈ 6.7 μs
