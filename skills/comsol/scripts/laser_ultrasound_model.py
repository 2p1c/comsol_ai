#!/usr/bin/env python3
"""
COMSOL Laser-Ultrasound Simulation: 1064nm Laser on 2mm Aluminum Plate
======================================================================

Models pulsed laser excitation of guided waves (Lamb waves) in a thin
aluminum plate and collects ultrasonic time signals at a square lattice
array of receiving points.

Physics coupling:
  Heat Transfer in Solids  --[Thermal Expansion]-->  Solid Mechanics
       (laser heating)                                (elastic waves)

The laser pulse is modeled as a Gaussian-distributed boundary heat source
(thermoelastic regime, absorbed energy ~0.1 mJ).

References:
  - mph library:   https://github.com/mph-py/mph
  - COMSOL API:    https://www.comsol.com/support/learning-center/article/
                    overview-of-the-comsol-api-107912

Usage:
  1. pip install -r requirements.txt
  2. Edit CONFIG below to adjust parameters
  3. python laser_ultrasound_model.py               # full run
     python laser_ultrasound_model.py --build-only  # stop after saving .mph
  4. Results appear in output/ directory
"""

import mph
import jpype
import numpy as np
import argparse
from pathlib import Path
import sys
import json
import time as _time
from datetime import datetime

# ===========================================================================
# Configuration
# ===========================================================================

CONFIG = {
    # --- Plate (reduced size to control mesh DOFs) ---
    "plate_Lx": 20.0,       # mm
    "plate_Ly": 20.0,       # mm
    "plate_Lz": 2.0,        # mm (thickness)

    # --- Laser (1064 nm, thermoelastic regime) ---
    # sigma_s = spot_radius/2. Min sigma ~5mm required to prevent exp()
    # underflow at plate corners via the COMSOL client API (verified: D < 1e-5
    # causes exp(-large) → 0 globally). For tighter spots, open .mph in GUI.
    "laser_x0": 10.0,                # mm (center of plate)
    "laser_y0": 10.0,                # mm
    "laser_spot_radius": 10.0,       # mm, 1/e^2 radius (sigma=5mm, min for API exp)
    "laser_pulse_width": 500.0e-9,   # s, square pulse width (500 ns)
    "laser_absorbed_energy": 0.1e-3, # J  (0.1 mJ)

    # --- Material: Aluminum 6061-T6 ---
    "material_E":      69e9,       # Pa
    "material_nu":     0.33,       # 1
    "material_rho":    2700,       # kg/m³
    "material_k":      167,        # W/(m·K)
    "material_Cp":     896,        # J/(kg·K)
    "material_alpha":  23.6e-6,    # 1/K
    "material_T0":     293.15,     # K

    # --- Receiving array ---
    "array_N": 5,                # 5×5 square grid (25 pts, enough for spatial sampling)
    "array_spacing": 2.0,        # mm
    "array_z_surface": "top",    # "top" or "bottom"

    # --- Mesh (3-tier: spot << wave_region << outer) ---
    "mesh_spot_size":   0.1,     # mm, ultra-fine at laser spot (resolves heat source)
    "mesh_spot_radius": 2.0,     # mm, radius of spot-refinement region
    "mesh_fine_size":   0.5,     # mm, wave propagation region
    "mesh_fine_radius": 8.0,     # mm, radius of wave-refinement region
    "mesh_coarse_size": 2.0,     # mm, outer region

    # --- Study (shorter duration, fewer steps) ---
    "study_t_start": 0.0,        # s
    "study_t_end":   5.0e-6,     # s  (5 us: S0 arrives ~1.8us, A0 arrives ~3.3us at 10mm)
    "study_t_step":   10.0e-9,   # s  (10 ns, 500 steps)

    # --- Output ---
    "output_dir":    "output",
    "model_filename": "laser_ultrasound_model.mph",
}

# ===========================================================================
# Derived quantities
# ===========================================================================

def compute_derived(cfg):
    d = {}
    # Spatial sigma: 1/e² radius w0 -> sigma = w0/2
    d["sigma_s"] = cfg["laser_spot_radius"] / 2.0
    # For uniform square pulse on the spot area: Q0 = E / (π * w0^2 * tau)
    w0_m = cfg["laser_spot_radius"] * 1e-3
    tau = cfg["laser_pulse_width"]
    d["Q0"] = cfg["laser_absorbed_energy"] / (np.pi * w0_m**2 * tau)  # W/m^2
    d["array_z"] = cfg["plate_Lz"] if cfg["array_z_surface"] == "top" else 0.0
    d["n_steps"] = int(
        (cfg["study_t_end"] - cfg["study_t_start"]) / cfg["study_t_step"]
    ) + 1
    return d


def generate_array_points(cfg, derived):
    N, sp = cfg["array_N"], cfg["array_spacing"]
    cx, cy = cfg["laser_x0"], cfg["laser_y0"]
    z = derived["array_z"]
    offset = (N - 1) * sp / 2.0
    pts = []
    for i in range(N):
        for j in range(N):
            pts.append({
                "i": i, "j": j,
                "label": f"P_{i}_{j}",
                "x": cx - offset + i * sp,
                "y": cy - offset + j * sp,
                "z": z,
            })
    return pts


# ===========================================================================
# Model builder  (uses the COMSOL Java API via mph's model.java bridge)
# ===========================================================================

def build_model(cfg, derived, array_points):
    """Create the complete COMSOL model and return (mph_model, java_model)."""

    print("\n" + "=" * 62)
    print("  COMSOL Laser-Ultrasound Simulation")
    print("  1064 nm laser -> 2 mm Al plate -> guided waves -> array export")
    print("=" * 62)

    # ---- [1] Start COMSOL ----
    print("\n[1/9] Starting COMSOL ...")
    mph.option("session", "stand-alone")       # Windows: fast stand-alone mode
    try:
        client = mph.start(cores=4)
    except Exception:
        mph.option("session", "client-server")
        client = mph.start(cores=4)
    print("  OK")

    # We keep both wrappers:
    #   pymodel  – mph Python wrapper  (save / solve / parameters)
    #   model    – COMSOL Java ModelClient (physics / mesh / probes / study)
    pymodel = client.create("Laser_Ultrasound_Al_Plate")
    model = pymodel.java

    # ---- [2] Global parameters ----
    print("\n[2/9] Global parameters ...")
    param = model.param()
    param.set("Lx",       f'{cfg["plate_Lx"]} [mm]')
    param.set("Ly",       f'{cfg["plate_Ly"]} [mm]')
    param.set("Lz",       f'{cfg["plate_Lz"]} [mm]')
    param.set("x0",       f'{cfg["laser_x0"]} [mm]')
    param.set("y0",       f'{cfg["laser_y0"]} [mm]')
    param.set("sigma_s",  f'{derived["sigma_s"]} [mm]')
    param.set("pw",       f'{cfg["laser_pulse_width"]} [s]')
    param.set("Q0",       f'{derived["Q0"]} [W/m^2]')
    param.set("T_amb",    f'{cfg["material_T0"]} [K]')
    param.set("h_spot",   f'{cfg["mesh_spot_size"]} [mm]')
    param.set("r_spot",   f'{cfg["mesh_spot_radius"]} [mm]')
    param.set("h_fine",   f'{cfg["mesh_fine_size"]} [mm]')
    param.set("h_coarse", f'{cfg["mesh_coarse_size"]} [mm]')
    param.set("r_fine",   f'{cfg["mesh_fine_radius"]} [mm]')
    print("  OK")

    # ---- [3] Geometry: 3-D block ----
    print("\n[3/9] Geometry ...")
    # Create component in the Java model tree (required by Java API)
    model.modelNode().create("comp1")
    model.geom().create("geom1", 3)
    model.geom("geom1").feature().create("blk1", "Block")
    model.geom("geom1").feature("blk1").set("size", ["Lx", "Ly", "Lz"])
    model.geom("geom1").run("fin")

    comp = model.component("comp1")
    print(f"  Plate: {cfg['plate_Lx']} x {cfg['plate_Ly']} x {cfg['plate_Lz']} mm")
    print(f"  Laser spot: ({cfg['laser_x0']}, {cfg['laser_y0']}) mm")
    print(f"  Array: {cfg['array_N']}x{cfg['array_N']} ({len(array_points)} pts), "
          f"spacing {cfg['array_spacing']} mm")

    # ---- [4] Material: Aluminum 6061-T6 ----
    print("\n[4/9] Material ...")
    mat = comp.material().create("mat1", "Common")
    mat.label("Aluminum 6061-T6")
    mat.selection().all()
    # Material properties live under the 'def' property group
    grp = mat.propertyGroup("def")
    grp.set("density",                   f'{cfg["material_rho"]} [kg/m^3]')
    grp.set("youngsmodulus",             f'{cfg["material_E"]} [Pa]')
    grp.set("poissonsratio",             str(cfg["material_nu"]))
    grp.set("thermalconductivity",       f'{cfg["material_k"]} [W/(m*K)]')
    grp.set("heatcapacity",              f'{cfg["material_Cp"]} [J/(kg*K)]')
    grp.set("thermalexpansioncoefficient", f'{cfg["material_alpha"]} [1/K]')
    print("  Aluminum 6061-T6 assigned to all domains")

    # ---- [5] Physics: Heat Transfer ----
    print("\n[5/9] Physics (Heat Transfer + Solid Mechanics) ...")
    ht = comp.physics().create("ht", "HeatTransfer", "geom1")
    ht.label("Heat Transfer in Solids")
    ht.feature("init1").set("Tinit", "T_amb")

    # Laser heat source on top surface (boundary 6)
    # Use spatial Gaussian + temporal square pulse.
    # sigma_s must be >= 5mm for the client API (exp underflow threshold D=5e-5).
    bhs = ht.feature().create("bhs1", "BoundaryHeatSource", 2)
    bhs.label("Laser Source (1064 nm)")
    bhs.selection().set(jpype.JArray(jpype.JInt, 1)([6]))
    bhs.set("Qb",
        "Q0 * exp(-((x-x0)^2+(y-y0)^2)/(2*sigma_s^2)) * (t > 0) * (t < pw)"
    )
    print(f"  Laser: spot {cfg['laser_spot_radius']:.1f} mm, pulse 0–{cfg['laser_pulse_width']*1e9:.0f} ns")
    print(f"  Q0 = {derived['Q0']:.2e} W/m^2")

    # ---- [6] Physics: Solid Mechanics ----
    solid = comp.physics().create("solid", "SolidMechanics", "geom1")
    solid.label("Solid Mechanics")
    # Free boundary is the default — all boundaries are free unless overridden

    # Low-reflecting boundaries on the four side faces (boundaries 2,3,4,5)
    try:
        lrb = solid.feature().create("lrb1", "LowReflectingBoundary", 2)
        lrb.selection().set(jpype.JArray(jpype.JInt, 1)([2, 3, 4, 5]))
        lrb.label("Absorbing Sides")
        print("  Low-reflecting boundaries set on side faces")
    except Exception:
        print("  (low-reflecting boundaries skipped -- free edges used)")

    # ---- [7] Thermal Expansion (via Linear Elastic Material sub-feature) ----
    print("\n[7/9] Thermal Expansion coupling ...")
    # NOTE: The multiphysics-level ThermalExpansion node does not correctly
    # couple via the client API. Instead, add ThermalExpansion directly to
    # the Linear Elastic Material node in Solid Mechanics.
    lemm = solid.feature("lemm1")
    tef = lemm.feature().create("tef1", "ThermalExpansion")
    tef.set("Tref", "T_amb")
    tef.set("alpha", f'{cfg["material_alpha"]} [1/K]')
    print("  Thermal expansion: alpha = 23.6e-6 1/K, Tref = T_amb")

    # ---- [8] Mesh (3-tier: spot < wave_region < outer) ----
    print("\n[8/9] Meshing ...")
    mesh = comp.mesh().create("mesh1")
    mesh.feature("size").set("hmax", "h_coarse")
    mesh.feature("size").set("hmin", "0.01 [mm]")

    # Tier 1: ultra-fine at laser spot (captures narrow Gaussian heat source)
    size_spot = mesh.feature().create("size_spot", "Size")
    size_spot.label("Spot Refinement")
    size_spot.set("hmax", "h_spot")
    spot_sel = comp.selection().create("sel_spot", "Ball")
    spot_sel.set("entitydim", "3")
    spot_sel.set("posx", "x0")
    spot_sel.set("posy", "y0")
    spot_sel.set("posz", "Lz/2")
    spot_sel.set("r", "r_spot")
    size_spot.selection().named("sel_spot")

    # Tier 2: fine in wave propagation region (resolves guided wavelengths)
    size_fine = mesh.feature().create("size_fine", "Size")
    size_fine.label("Wave Region")
    size_fine.set("hmax", "h_fine")
    fine_sel = comp.selection().create("sel_wave_region", "Ball")
    fine_sel.set("entitydim", "3")
    fine_sel.set("posx", "x0")
    fine_sel.set("posy", "y0")
    fine_sel.set("posz", "Lz/2")
    fine_sel.set("r", "r_fine")
    size_fine.selection().named("sel_wave_region")

    mesh.feature().create("ftet1", "FreeTet")
    mesh.run()
    print(f"  Spot: {cfg['mesh_spot_size']} mm / Wave: {cfg['mesh_fine_size']} mm / Outer: {cfg['mesh_coarse_size']} mm")

    # ---- Save pre-solve backup ----
    import uuid
    pre_solve_name = f"_pre_solve_{uuid.uuid4().hex[:8]}.mph"
    pymodel.save(pre_solve_name)
    print(f"  Pre-solve model saved -> {pre_solve_name}")

    return client, pymodel, model, pre_solve_name


# ===========================================================================
# Study, solve, data extraction, export
# ===========================================================================


def setup_study(model_java, cfg, derived):
    """Create the time-dependent study step."""
    print("\n[Study] Time-dependent step ...")
    study = model_java.study().create("std1")
    study.label("Laser Ultrasound – Time Dependent")
    step = study.feature().create("time", "Transient")
    step.label("Time Dependent")
    step.set("tlist",
        f"range({cfg['study_t_start']}, {cfg['study_t_step']}, {cfg['study_t_end']})"
    )
    step.set("rtol", "1e-5")
    step.set("plot", "on")            # convergence plots (GUI only)
    step.set("probesel", "all")       # record all probes
    print(f"  {cfg['study_t_start']*1e6:.1f} – {cfg['study_t_end']*1e6:.1f} us, "
          f"dt={cfg['study_t_step']*1e9:.0f} ns, {derived['n_steps']} outputs")


def solve_model(pymodel, cfg, model_path, output_dir):
    """Solve via mph (keeps solution data for extraction)."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    print(f"\n[9/9] Solving via mph ...")
    print(f"  Press Ctrl+C to stop early (partial results will be saved).")

    t0 = _time.time()
    try:
        pymodel.solve()
        print(f"  Done in {_time.time() - t0:.0f} s")
        return True
    except Exception as e:
        print(f"  Solver error: {e}")
        return False


def extract_via_evaluate(pymodel, array_points, derived):
    """Extract time series via mph evaluate + nearest-node lookup.

    pymodel.evaluate('w', 'mm') returns (n_timesteps, n_nodes) for ALL mesh nodes.
    We find the nodes nearest to each array point and extract their time series.
    """
    print("\n  Extracting data via mph.evaluate + nearest-node ...")

    n_steps = derived["n_steps"]
    n_pts = len(array_points)
    times = np.linspace(CONFIG["study_t_start"], CONFIG["study_t_end"], n_steps)

    # Get coordinates at t=0 (undeformed mesh)
    x0 = pymodel.evaluate("x", "mm")
    y0 = pymodel.evaluate("y", "mm")
    z0 = pymodel.evaluate("z", "mm")
    # These are (n_timesteps, n_nodes) — take first timestep
    coords = np.column_stack([
        np.atleast_1d(np.squeeze(x0[0])),
        np.atleast_1d(np.squeeze(y0[0])),
        np.atleast_1d(np.squeeze(z0[0])),
    ])
    n_nodes = coords.shape[0]
    print(f"  Mesh nodes: {n_nodes}")

    # Evaluate w at all nodes and timesteps
    w_all = pymodel.evaluate("w", "mm")  # (n_timesteps, n_nodes)
    print(f"  w shape: {w_all.shape}")
    if np.max(np.abs(w_all)) < 1e-12:
        print("  WARNING: All displacements are zero. Check heat source.")
        displacements = np.zeros((n_pts, n_steps))
        return times, displacements, []

    # For each array point, find nearest mesh node
    displacements = np.full((n_pts, n_steps), np.nan)
    found = 0
    for idx, pt in enumerate(array_points):
        pt_coord = np.array([pt["x"], pt["y"], pt["z"]])
        dists = np.linalg.norm(coords - pt_coord, axis=1)
        nearest = np.argmin(dists)
        if dists[nearest] < 1.0:  # within 1mm
            displacements[idx, :] = w_all[:, nearest]
            found += 1

    print(f"  {found}/{n_pts} points matched to mesh nodes")
    return times, displacements, []


def export_results(times, displacements, array_points, cfg, derived, output_dir):
    """Write .npz, per-point .csv, and metadata."""
    print("\n  Writing output files ...")
    output_dir.mkdir(parents=True, exist_ok=True)

    # ---- NPZ (primary archive) ----
    npz = output_dir / "laser_ultrasound_data.npz"
    np.savez_compressed(
        npz,
        times=times,
        displacements=displacements,
        array_coords=np.array([[p["x"], p["y"], p["z"]] for p in array_points]),
        array_labels=np.array([p["label"] for p in array_points]),
        config_json=json.dumps(cfg, indent=2),
    )
    print(f"  {npz}")

    # ---- CSV time-series ----
    csv_dir = output_dir / "csv_timeseries"
    csv_dir.mkdir(exist_ok=True)
    for idx, pt in enumerate(array_points):
        w = displacements[idx]
        with open(csv_dir / f"w_{pt['label']}.csv", "w") as f:
            f.write("time_s,w_mm\n")
            for ti, t in enumerate(times):
                val = w[ti]
                f.write(f"{t:.12e},{'' if np.isnan(val) else val}\n")

    # ---- Summary CSV ----
    import pandas as pd
    rows = []
    for idx, pt in enumerate(array_points):
        w = displacements[idx]
        ok = ~np.isnan(w)
        rows.append({
            "label": pt["label"], "i": pt["i"], "j": pt["j"],
            "x_mm": pt["x"], "y_mm": pt["y"],
            "p2p_mm": np.ptp(w[ok]) if ok.any() else np.nan,
            "max_abs_mm": np.max(np.abs(w[ok])) if ok.any() else np.nan,
        })
    pd.DataFrame(rows).to_csv(output_dir / "amplitude_summary.csv", index=False)

    # ---- Metadata JSON ----
    meta = {
        "timestamp": datetime.now().isoformat(),
        "config": {k: str(v) if isinstance(v, float) else v for k, v in cfg.items()},
        "derived": {k: str(v) if isinstance(v, float) else v for k, v in derived.items()},
        "n_array_points": len(array_points),
        "n_timesteps": len(times),
        "time_unit": "s",
        "displacement_unit": "mm",
    }
    with open(output_dir / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2, default=str)

    print(f"  {csv_dir}/  ({len(array_points)} files)")
    print(f"  {output_dir / 'amplitude_summary.csv'}")
    print(f"  {output_dir / 'metadata.json'}")


# ===========================================================================
# Main
# ===========================================================================

def main(args=None):
    t_start = _time.time()

    # ---- Parse arguments ----
    parser = argparse.ArgumentParser(
        description="COMSOL laser-ultrasound simulation on Al plate"
    )
    parser.add_argument(
        "--build-only", action="store_true",
        help="Build model and save .mph, then stop (skip solving)."
    )
    parser.add_argument(
        "--config", type=str, default=None,
        help="Path to a JSON config file to override defaults."
    )
    parsed = parser.parse_args(args)

    # Load external config if provided
    cfg = dict(CONFIG)  # copy defaults
    if parsed.config:
        import json as _json
        with open(parsed.config) as f:
            cfg.update(_json.load(f))

    derived = compute_derived(cfg)
    array_points = generate_array_points(cfg, derived)

    # ---- Print summary ----
    print(f"\n  {'-'*56}")
    print(f"  Plate:     {cfg['plate_Lx']} x {cfg['plate_Ly']} x {cfg['plate_Lz']} mm")
    print(f"  Laser:     spot {cfg['laser_spot_radius']:.1f} mm, "
          f"{cfg['laser_pulse_width']*1e9:.0f} ns pulse, "
          f"Q0 = {derived['Q0']:.2e} W/m^2")
    print(f"  Array:     {cfg['array_N']}x{cfg['array_N']} ({len(array_points)} pts), "
          f"{cfg['array_spacing']} mm spacing")
    print(f"  Mesh:      spot {cfg['mesh_spot_size']} mm / wave {cfg['mesh_fine_size']} mm / outer {cfg['mesh_coarse_size']} mm")
    print(f"  Study:     {cfg['study_t_start']*1e6:.0f}–{cfg['study_t_end']*1e6:.0f} us, "
          f"dt = {cfg['study_t_step']*1e9:.0f} ns ({derived['n_steps']} outputs)")
    if parsed.build_only:
        print(f"  Mode:      BUILD ONLY (no solve)")
    print(f"  {'-'*56}")

    # ---- Build ----
    client, pymodel, java_model, pre_solve_name = build_model(cfg, derived, array_points)
    setup_study(java_model, cfg, derived)

    # Save a copy with the configured name (for the user)
    try:
        pymodel.save(cfg["model_filename"])
        print(f"  Copy saved -> {cfg['model_filename']}")
    except Exception:
        print(f"  (could not save {cfg['model_filename']} — use {pre_solve_name} instead)")

    # ---- Stop here if --build-only ----
    if parsed.build_only:
        print(f"\n{'='*62}")
        print(f"  Build-only mode: stopping before solve.")
        print(f"  Inspect '{pre_solve_name}' in the COMSOL GUI,")
        print(f"  then re-run without --build-only to solve and export.")
        print(f"{'='*62}\n")
        return 0

    # ---- Solve ----
    output_dir = Path(cfg["output_dir"])
    ok = solve_model(pymodel, cfg, pre_solve_name, str(output_dir))
    if not ok:
        return 1

    # ---- Extract & export ----
    times, displacements, _missing = extract_via_evaluate(
        pymodel, array_points, derived
    )
    export_results(times, displacements, array_points, cfg, derived, output_dir)

    # Save solved model
    solved_path = output_dir / "solved_model.mph"
    try:
        pymodel.save(str(solved_path))
        print(f"  Solved model saved -> {solved_path}")
    except Exception:
        pass

    # ---- Animate ----
    try:
        from animate_results import make_animation, load_surface_field
        print("\n  Generating wave animation ...")
        xs, ys, ws, n_steps = load_surface_field(pymodel)
        ani_path = output_dir / "wave_animation.mp4"
        times_arr = np.linspace(cfg["study_t_start"], cfg["study_t_end"], derived["n_steps"])
        make_animation(xs, ys, ws, n_steps, ani_path, times_arr, fps=15)
    except Exception as e:
        print(f"  Animation skipped: {e}")

    # ---- Summary ----
    valid = int(np.sum(~np.all(np.isnan(displacements), axis=1)))
    print(f"\n{'='*62}")
    print(f"  Done in {_time.time() - t_start:.0f} s")
    print(f"  Valid signals: {valid}/{len(array_points)}")
    print(f"  Output:        {output_dir.resolve()}")
    print(f"{'='*62}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
