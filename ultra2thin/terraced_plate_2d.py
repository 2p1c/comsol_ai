#!/usr/bin/env python3
"""
COMSOL 2D Terraced Aluminum Plate — Ultrasonic Guided Wave Simulation
======================================================================

Models a 200 mm aluminum plate with random terrace-step thinning (1–4 mm,
2–4 levels) in the thickness direction.  Excitation is a prescribed surface
displacement (time-domain signal) applied to the top edge — mimicking the
mechanical effect of a pulsed laser in the thermoelastic regime.

Physics:  2D Solid Mechanics (plane strain)
Geometry: Polygon cross-section with stepped bottom (terraced thinning)

Usage:
  python terraced_plate_2d.py                 # build, solve, export
  python terraced_plate_2d.py --build-only    # build and save .mph only
  python terraced_plate_2d.py --seed 123      # different random terrace layout
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
    # --- Plate ---
    "plate_Lx": 200.0,             # mm, total length
    "plate_max_thickness": 4.0,    # mm, thickest section
    "plate_min_thickness": 1.0,    # mm, thinnest section
    "n_terraces": 3,               # number of terrace levels (2–4)
    "random_seed": 42,

    # --- Prescribed displacement (excitation) ---
    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  TODO: Replace with your time-domain displacement formula.      ║
    # ║  COMSOL variables available:  t (time), x, y (spatial coords). ║
    # ║  Example:  "A0 * sin(2*pi*f*t) * exp(-((t-t0)/tau)^2)"         ║
    # ╚══════════════════════════════════════════════════════════════════╝
    "prescribed_disp_formula": "0 [mm]",  # <-- USER: put your formula here

    # --- Material:  Aluminum 6061-T6 ---
    "material_E":    69e9,         # Pa,  Young's modulus
    "material_nu":   0.33,         # 1,   Poisson's ratio
    "material_rho":  2700,         # kg/m^3, density

    # --- Receivers (points along the top surface) ---
    "array_N": 20,                 # number of receiving points
    "array_x_margin": 10.0,        # mm, distance from each end

    # --- Mesh ---
    "mesh_max_size": 0.5,          # mm, global maximum element size
    "mesh_min_size": 0.02,         # mm, global minimum

    # --- Study ---
    "study_t_start": 0.0,          # s
    "study_t_end":   50.0e-6,      # s  (50 us)
    "study_t_step":   0.1e-6,      # s  (100 ns)
    "study_rtol":     "1e-5",

    # --- Output ---
    "output_dir":     "output",
    "model_filename": "terraced_plate_2d.mph",
}


# ===========================================================================
# Terrace geometry generator
# ===========================================================================

def generate_terraces(cfg):
    """Random terrace step thinning: section boundaries + thicknesses.

    Returns (section_boundaries, thicknesses, max_t) where
    - section_boundaries[i] = x_start of section i (0-indexed, length N+1)
    - thicknesses[i]      = thickness of section i  (mm)
    - max_t               = thickest section (top-surface y coordinate)
    """
    rng = np.random.RandomState(cfg["random_seed"])
    n = cfg["n_terraces"]
    Lx = cfg["plate_Lx"]
    t_min = cfg["plate_min_thickness"]
    t_max = cfg["plate_max_thickness"]

    # n random thicknesses in [t_min, t_max], sorted thick→thin for terraced look
    thicknesses = np.sort(rng.uniform(t_min, t_max, n))[::-1]
    thicknesses[0] = t_max      # ensure extremes present
    thicknesses[-1] = t_min

    # Divide plate length into n unequal sections (min 15 mm each)
    if n == 1:
        boundaries = np.array([0.0, Lx])
    else:
        min_gap = 15.0
        # place n-1 cut points
        low = min_gap
        high = Lx - min_gap
        cuts = sorted(rng.uniform(low, high, n - 1))
        boundaries = np.array([0.0] + list(cuts) + [Lx])

    print("  Terrace layout (left → right):")
    for i in range(n):
        x0, x1 = boundaries[i], boundaries[i + 1]
        print(f"    [{x0:7.1f} – {x1:7.1f}] mm   thickness = {thicknesses[i]:.1f} mm"
              f"  ({'thickest' if thicknesses[i]==t_max else 'thinnest' if thicknesses[i]==t_min else 'intermediate'})")

    return boundaries, thicknesses, t_max


# ===========================================================================
# Derived quantities
# ===========================================================================

def compute_derived(cfg):
    d = {}
    d["n_steps"] = int(
        (cfg["study_t_end"] - cfg["study_t_start"]) / cfg["study_t_step"]
    ) + 1
    return d


def generate_receivers(cfg, max_t):
    """Place receiving points evenly along the top surface."""
    N = cfg["array_N"]
    margin = cfg["array_x_margin"]
    x_pos = np.linspace(margin, cfg["plate_Lx"] - margin, N)
    pts = []
    for i, x in enumerate(x_pos):
        pts.append({
            "i": i,
            "label": f"P{i:02d}",
            "x": round(x, 4),
            "y": max_t,
        })
    return pts


# ===========================================================================
# Polygon vertex builder (terraced cross-section)
# ===========================================================================

def build_polygon_vertices(boundaries, thicknesses, max_t):
    """Build x,y vertex arrays for a 2D polygon with stepped bottom.

    The polygon traces counter-clockwise:
      bottom edge (stepped) → right edge → top edge (flat) → auto-close

    Returns (x_coords, y_coords, top_boundary_num).
    Boundary numbers are 1-based.
    """
    n = len(thicknesses)
    x = []
    y = []

    # --- Bottom edge, left to right (stepped) ---
    for i in range(n):
        x0 = boundaries[i]
        x1 = boundaries[i + 1]
        y_bottom = max_t - thicknesses[i]
        x.append(x0)
        y.append(y_bottom)
        x.append(x1)
        y.append(y_bottom)

    # --- Right edge (up to top surface) ---
    x.append(boundaries[-1])   # Lx
    y.append(max_t)

    # --- Top edge (flat, right → left) ---
    x.append(0.0)
    y.append(max_t)

    # COMSOL auto-closes the polygon back to the first vertex.

    # Boundary numbering (1-based, polygon auto-closes):
    #   n bottom edges      → boundaries 1,3,5,...,2n-1
    #   n-1 vertical steps  → boundaries 2,4,...,2n-2
    #   right edge          → boundary 2n
    #   top edge            → boundary 2n+1
    #   left edge           → boundary 2n+2 (auto-close back to v1)
    n_vertices = len(x)
    top_boundary   = 2 * n + 1
    right_boundary = 2 * n
    left_boundary  = 2 * n + 2

    return x, y, top_boundary, right_boundary, left_boundary


# ===========================================================================
# Model builder
# ===========================================================================

def build_model(cfg, derived, receivers, boundaries, thicknesses, max_t):
    """Create the complete 2D COMSOL model."""

    print("\n" + "=" * 62)
    print("  COMSOL 2D Terraced Plate — Ultrasonic Guided Waves")
    print("  Prescribed surface displacement (laser-mimic excitation)")
    print("=" * 62)

    # ---- [1] Start COMSOL ----
    print("\n[1/7] Starting COMSOL ...")
    mph.option("session", "stand-alone")
    try:
        client = mph.start(cores=4)
    except Exception:
        mph.option("session", "client-server")
        client = mph.start(cores=4)
    print("  OK")

    pymodel = client.create("Terraced_Plate_2D")
    model = pymodel.java

    # ---- Build polygon vertices from terrace layout ----
    vert_x, vert_y, top_bnd, right_bnd, left_bnd = \
        build_polygon_vertices(boundaries, thicknesses, max_t)

    # ---- [2] Global parameters ----
    print("\n[2/7] Global parameters ...")
    param = model.param()
    param.set("Lx",    f'{cfg["plate_Lx"]} [mm]')
    param.set("T_max", f'{cfg["plate_max_thickness"]} [mm]')
    param.set("T_min", f'{cfg["plate_min_thickness"]} [mm]')
    param.set("h_max", f'{cfg["mesh_max_size"]} [mm]')
    param.set("h_min", f'{cfg["mesh_min_size"]} [mm]')
    param.set("disp_expr", cfg["prescribed_disp_formula"])
    print("  OK")

    # ---- [3] Geometry: 2D polygon ----
    print("\n[3/7] Geometry (2D polygon with terraced bottom) ...")
    model.modelNode().create("comp1")
    model.geom().create("geom1", 2)           # 2 = 2D

    n_vert = len(vert_x)
    pol = model.geom("geom1").feature().create("pol1", "Polygon")
    # Pass coordinates as space-separated strings (COMSOL default length unit = mm)
    pol.set("x", " ".join(str(v) for v in vert_x))
    pol.set("y", " ".join(str(v) for v in vert_y))
    model.geom("geom1").run("fin")

    comp = model.component("comp1")
    print(f"  Plate: {cfg['plate_Lx']} mm x {cfg['plate_max_thickness']} mm max")
    print(f"  Terrace levels: {cfg['n_terraces']}  "
          f"(min {cfg['plate_min_thickness']:.1f} mm, max {cfg['plate_max_thickness']:.1f} mm)")
    print(f"  Top boundary: {top_bnd}  |  Right: {right_bnd}  |  Left: {left_bnd}")

    # ---- [4] Material ----
    print("\n[4/7] Material (Aluminum 6061-T6) ...")
    mat = comp.material().create("mat1", "Common")
    mat.label("Aluminum 6061-T6")
    mat.selection().all()
    grp = mat.propertyGroup("def")
    grp.set("density",       f'{cfg["material_rho"]} [kg/m^3]')
    grp.set("youngsmodulus", f'{cfg["material_E"]} [Pa]')
    grp.set("poissonsratio", str(cfg["material_nu"]))
    print("  OK")

    # ---- [5] Physics: 2D Solid Mechanics (plane strain) ----
    print("\n[5/7] Physics (Solid Mechanics, plane strain) ...")
    solid = comp.physics().create("solid", "SolidMechanics", "geom1")
    solid.label("Solid Mechanics (plane strain)")

    # Prescribed displacement on top surface — the laser-mimic excitation
    pd = solid.feature().create("pd1", "PrescribedDisplacement", 1)   # dim=1 (edge)
    pd.label("Laser-Mimic Excitation")
    pd.selection().set(jpype.JArray(jpype.JInt, 1)([top_bnd]))
    pd.set("u0", "0")                    # no in-plane displacement
    pd.set("v0", "disp_expr")            # out-of-plane = user formula
    print(f"  Prescribed displacement on top edge (boundary {top_bnd})")
    print(f"    u0 = 0")
    print(f"    v0 = {cfg['prescribed_disp_formula']}")

    # Low-reflecting boundaries on left and right edges (absorb outgoing waves)
    lrb_indices = [left_bnd, right_bnd]
    try:
        lrb = solid.feature().create("lrb1", "LowReflectingBoundary", 1)
        lrb.selection().set(jpype.JArray(jpype.JInt, 1)(lrb_indices))
        lrb.label("Absorbing Sides")
        print(f"  Low-reflecting boundaries on left + right edges ({lrb_indices})")
    except Exception as e:
        print(f"  (low-reflecting boundaries skipped: {e})")

    # ---- [6] Mesh ----
    print("\n[6/7] Meshing ...")
    mesh = comp.mesh().create("mesh1")
    mesh.feature("size").set("hmax", "h_max")
    mesh.feature("size").set("hmin", "h_min")
    mesh.feature().create("ftri1", "FreeTri")
    mesh.run()
    print(f"  Free triangular mesh:  h_max = {cfg['mesh_max_size']} mm,  "
          f"h_min = {cfg['mesh_min_size']} mm")

    # ---- [7] Study ----
    print("\n[7/7] Study (time-dependent) ...")
    study = model.study().create("std1")
    study.label("Ultrasonic Waves – Time Dependent")
    step = study.feature().create("time", "Transient")
    step.label("Time Dependent")
    step.set("tlist",
        f"range({cfg['study_t_start']}, {cfg['study_t_step']}, {cfg['study_t_end']})"
    )
    step.set("rtol", cfg["study_rtol"])
    step.set("plot", "on")
    step.set("probesel", "all")
    print(f"  t = {cfg['study_t_start']*1e6:.1f} – {cfg['study_t_end']*1e6:.1f} us"
          f"  |  dt = {cfg['study_t_step']*1e9:.0f} ns"
          f"  |  {derived['n_steps']} outputs")

    # ---- Save pre-solve ----
    import uuid
    pre_solve_name = f"_pre_solve_{uuid.uuid4().hex[:8]}.mph"
    pymodel.save(pre_solve_name)
    print(f"  Pre-solve model saved -> {pre_solve_name}")

    return client, pymodel, model, pre_solve_name, max_t


# ===========================================================================
# Solve
# ===========================================================================

def solve_model(pymodel, cfg):
    """Solve via mph (preserves solution data for extraction)."""
    output_dir = Path(cfg["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  Solving (time-domain transient) ...")
    print(f"  Press Ctrl+C to stop early (partial results will be saved).")

    t0 = _time.time()
    try:
        pymodel.solve()
        print(f"  Done in {_time.time() - t0:.0f} s")
        return True
    except Exception as e:
        print(f"  Solver error: {e}")
        return False


# ===========================================================================
# Data extraction (mph.evaluate + nearest-node lookup)
# ===========================================================================

def extract_via_evaluate(pymodel, receivers, derived):
    """Extract displacement time series at each receiver via nearest-node."""

    print("\n  Extracting data via mph.evaluate + nearest-node ...")

    n_steps = derived["n_steps"]
    n_pts = len(receivers)
    times = np.linspace(CONFIG["study_t_start"], CONFIG["study_t_end"], n_steps)

    # Mesh node coordinates (static, t=0)
    x0 = pymodel.evaluate("x", "mm")
    y0 = pymodel.evaluate("y", "mm")
    coords = np.column_stack([
        np.atleast_1d(np.squeeze(x0[0])),
        np.atleast_1d(np.squeeze(y0[0])),
    ])
    n_nodes = coords.shape[0]
    print(f"  Mesh nodes: {n_nodes}")

    # Evaluate displacement fields
    u_all = pymodel.evaluate("u", "mm")   # x-displacement
    v_all = pymodel.evaluate("v", "mm")   # y-displacement
    print(f"  u shape: {u_all.shape},  v shape: {v_all.shape}")

    if np.max(np.abs(u_all)) < 1e-12 and np.max(np.abs(v_all)) < 1e-12:
        print("  WARNING: All displacements zero — check excitation formula.")

    u_signals = np.full((n_pts, n_steps), np.nan)
    v_signals = np.full((n_pts, n_steps), np.nan)
    found = 0

    for idx, pt in enumerate(receivers):
        pt_coord = np.array([pt["x"], pt["y"]])
        dists = np.linalg.norm(coords - pt_coord, axis=1)
        nearest = np.argmin(dists)
        if dists[nearest] < 1.0:          # within 1 mm — good match
            u_signals[idx, :] = u_all[:, nearest]
            v_signals[idx, :] = v_all[:, nearest]
            found += 1

    print(f"  {found}/{n_pts} receivers matched to mesh nodes")
    return times, u_signals, v_signals


# ===========================================================================
# Export
# ===========================================================================

def export_results(times, u_signals, v_signals, receivers, cfg, derived, output_dir):
    """Write .npz archive, per-point CSV files, and metadata."""

    print("\n  Writing output files ...")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ---- NPZ (primary archive) ----
    npz_path = output_dir / "terraced_plate_2d_data.npz"
    np.savez_compressed(
        npz_path,
        times=times,
        u_displacement=u_signals,
        v_displacement=v_signals,
        receiver_coords=np.array([[p["x"], p["y"]] for p in receivers]),
        receiver_labels=np.array([p["label"] for p in receivers]),
        config_json=json.dumps(cfg, indent=2),
    )
    print(f"  {npz_path}")

    # ---- Per-receiver CSV ----
    csv_dir = output_dir / "csv_timeseries"
    csv_dir.mkdir(exist_ok=True)
    for idx, pt in enumerate(receivers):
        with open(csv_dir / f"{pt['label']}.csv", "w") as f:
            f.write("time_s,u_mm,v_mm\n")
            for ti in range(len(times)):
                u_val = u_signals[idx, ti]
                v_val = v_signals[idx, ti]
                u_str = "" if np.isnan(u_val) else f"{u_val:.12e}"
                v_str = "" if np.isnan(v_val) else f"{v_val:.12e}"
                f.write(f"{times[ti]:.12e},{u_str},{v_str}\n")

    # ---- Summary CSV ----
    import pandas as pd
    rows = []
    for idx, pt in enumerate(receivers):
        v = v_signals[idx]
        ok = ~np.isnan(v)
        rows.append({
            "label":    pt["label"],
            "i":        pt["i"],
            "x_mm":     pt["x"],
            "y_mm":     pt["y"],
            "v_p2p_mm": np.ptp(v[ok]) if ok.any() else np.nan,
            "v_max_mm": np.max(np.abs(v[ok])) if ok.any() else np.nan,
        })
    pd.DataFrame(rows).to_csv(output_dir / "amplitude_summary.csv", index=False)

    # ---- Metadata ----
    meta = {
        "timestamp":       datetime.now().isoformat(),
        "config":          {k: str(v) if isinstance(v, float) else v for k, v in cfg.items()},
        "derived":         {k: str(v) if isinstance(v, float) else v for k, v in derived.items()},
        "n_receivers":     len(receivers),
        "n_timesteps":     len(times),
        "time_unit":       "s",
        "displacement_unit": "mm",
    }
    with open(output_dir / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2, default=str)

    print(f"  {csv_dir}/  ({len(receivers)} files)")
    print(f"  {output_dir / 'amplitude_summary.csv'}")
    print(f"  {output_dir / 'metadata.json'}")


# ===========================================================================
# Main
# ===========================================================================

def main(args=None):
    t_start = _time.time()

    parser = argparse.ArgumentParser(
        description="COMSOL 2D terraced plate — laser-mimic ultrasonic simulation"
    )
    parser.add_argument("--build-only", action="store_true",
                        help="Build model and save .mph, then stop (skip solve).")
    parser.add_argument("--seed", type=int, default=None,
                        help="Override random seed for terrace layout.")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to JSON config file to override defaults.")
    parsed = parser.parse_args(args)

    cfg = dict(CONFIG)
    if parsed.seed is not None:
        cfg["random_seed"] = parsed.seed
    if parsed.config:
        with open(parsed.config) as f:
            cfg.update(json.load(f))

    derived = compute_derived(cfg)

    # Placeholder warning
    if cfg["prescribed_disp_formula"] == "0 [mm]":
        print("\n  ╔" + "═" * 58 + "╗")
        print("  ║  NOTE: prescribed_disp_formula is still the placeholder '0 [mm]'.   ║")
        print("  ║  All displacements will be zero.                                      ║")
        print("  ║  Edit CONFIG['prescribed_disp_formula'] to set your excitation.       ║")
        print("  ╚" + "═" * 58 + "╝")

    # ---- Generate terrace layout (once) ----
    boundaries, thicknesses, max_t = generate_terraces(cfg)
    receivers = generate_receivers(cfg, max_t)

    # ---- Print summary ----
    print(f"\n  {'-'*56}")
    print(f"  Plate:     {cfg['plate_Lx']} mm x {cfg['plate_max_thickness']} mm (max)"
          f"  |  terraces: {cfg['n_terraces']}")
    print(f"  Excitation: v0 = {cfg['prescribed_disp_formula']}  (on top edge)")
    print(f"  Receivers:  {cfg['array_N']} pts along top surface")
    print(f"  Mesh:       h_max = {cfg['mesh_max_size']} mm")
    print(f"  Study:      {cfg['study_t_start']*1e6:.0f}–{cfg['study_t_end']*1e6:.0f} us"
          f"  |  dt = {cfg['study_t_step']*1e9:.0f} ns  ({derived['n_steps']} steps)")
    if parsed.build_only:
        print(f"  Mode:       BUILD ONLY (no solve)")
    print(f"  {'-'*56}")

    # ---- Build ----
    client, pymodel, java_model, pre_solve_name, max_t = \
        build_model(cfg, derived, receivers, boundaries, thicknesses, max_t)

    # Save a copy with the user-facing filename
    try:
        pymodel.save(cfg["model_filename"])
        print(f"  Copy saved -> {cfg['model_filename']}")
    except Exception:
        print(f"  (could not save {cfg['model_filename']} — use {pre_solve_name})")

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
    ok = solve_model(pymodel, cfg)
    if not ok:
        return 1

    # ---- Extract & export ----
    times, u_signals, v_signals = extract_via_evaluate(pymodel, receivers, derived)
    export_results(times, u_signals, v_signals, receivers, cfg, derived, output_dir)

    # Save solved model
    solved_path = output_dir / "solved_model.mph"
    try:
        pymodel.save(str(solved_path))
        print(f"  Solved model saved -> {solved_path}")
    except Exception:
        pass

    # ---- Summary ----
    valid = int(np.sum(~np.all(np.isnan(v_signals), axis=1)))
    print(f"\n{'='*62}")
    print(f"  Done in {_time.time() - t_start:.0f} s")
    print(f"  Valid signals: {valid}/{len(receivers)}")
    print(f"  Output:        {output_dir.resolve()}")
    print(f"{'='*62}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
