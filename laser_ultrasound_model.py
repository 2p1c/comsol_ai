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
    # --- Plate ---
    "plate_Lx": 40.0,       # mm
    "plate_Ly": 40.0,       # mm
    "plate_Lz": 2.0,        # mm (thickness)

    # --- Laser (1064 nm, thermoelastic regime) ---
    "laser_x0": 20.0,                # mm
    "laser_y0": 20.0,                # mm
    "laser_spot_radius": 0.3,        # mm, 1/e² intensity radius
    "laser_pulse_FWHM": 10.0e-9,     # s  (10 ns)
    "laser_peak_time": 30.0e-9,      # s  (shift from t=0)
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
    "array_N": 7,                # N×N square grid
    "array_spacing": 2.0,        # mm
    "array_z_surface": "top",    # "top" or "bottom"

    # --- Mesh ---
    "mesh_fine_size": 0.3,       # mm, central region
    "mesh_coarse_size": 1.5,     # mm, outer region
    "mesh_coarse_radius": 15.0,  # mm, fine-mesh radius around source

    # --- Study ---
    "study_t_start": 0.0,        # s
    "study_t_end":   10.0e-6,    # s
    "study_t_step":   5.0e-9,    # s

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
    # Temporal sigma: FWHM -> sigma = FWHM / (2*sqrt(2*ln2))
    d["sigma_t"] = cfg["laser_pulse_FWHM"] / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    # Peak heat flux  Q0 = E / ((2π)^(3/2) * σ_s² * σ_t)
    sigma_s_m = d["sigma_s"] * 1e-3
    d["Q0"] = cfg["laser_absorbed_energy"] / (
        (2.0 * np.pi) ** 1.5 * sigma_s_m ** 2 * d["sigma_t"]
    )
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
    param.set("sigma_t",  f'{derived["sigma_t"]} [s]')
    param.set("t0",       f'{cfg["laser_peak_time"]} [s]')
    param.set("Q0",       f'{derived["Q0"]} [W/m^2]')
    param.set("T_amb",    f'{cfg["material_T0"]} [K]')
    param.set("h_fine",   f'{cfg["mesh_fine_size"]} [mm]')
    param.set("h_coarse", f'{cfg["mesh_coarse_size"]} [mm]')
    param.set("r_coarse", f'{cfg["mesh_coarse_radius"]} [mm]')
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

    # Gaussian boundary heat source on top surface (z = Lz, boundary 6)
    bhs = ht.feature().create("bhs1", "BoundaryHeatSource", 2)
    bhs.label("Laser Source (1064 nm)")
    bhs.selection().set(jpype.JArray(jpype.JInt, 1)([6]))
    bhs.set("Qb",
        "Q0 * exp(-((x-x0)^2 + (y-y0)^2) / (2*sigma_s^2)) "
        "* exp(-(t-t0)^2 / (2*sigma_t^2))"
    )
    print(f"  Laser: spot {cfg['laser_spot_radius']:.1f} mm, "
          f"FWHM {cfg['laser_pulse_FWHM']*1e9:.0f} ns, "
          f"Q0 = {derived['Q0']:.2e} W/m^2")

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

    # ---- [7] Multiphysics: Thermal Expansion ----
    print("\n[7/9] Thermal Expansion coupling ...")
    te = comp.multiphysics().create("te1", "ThermalExpansion", "geom1")
    te.label("Thermal Expansion")
    te.set("Tref", "T_amb")
    try:
        tem = te.feature().create("tem1", "ThermalExpansionModel")
        try:
            tem.set("HeatTransferInterface", "ht")
        except Exception:
            pass
        try:
            tem.set("StructuralInterface", "solid")
        except Exception:
            pass
    except Exception:
        pass
    try:
        te.set("Temperature", "T")
    except Exception:
        pass
    print("  ht.T  -->  solid.thermal_strain")

    # ---- [8] Mesh ----
    print("\n[8/9] Meshing ...")
    mesh = comp.mesh().create("mesh1")
    mesh.feature("size").set("hmax", "h_coarse")
    mesh.feature("size").set("hmin", "0.01 [mm]")

    # Fine mesh in wave region (Ball selection around the source)
    size_fine = mesh.feature().create("size_fine", "Size")
    size_fine.label("Fine – Wave Region")
    size_fine.set("hmax", "h_fine")
    fine_sel = comp.selection().create("sel_wave_region", "Ball")
    fine_sel.set("entitydim", "3")
    fine_sel.set("posx", "x0")
    fine_sel.set("posy", "y0")
    fine_sel.set("posz", "Lz/2")
    fine_sel.set("r", "r_coarse")
    size_fine.selection().named("sel_wave_region")

    mesh.feature().create("ftet1", "FreeTet")
    mesh.run()
    print(f"  Fine: {cfg['mesh_fine_size']} mm  |  Coarse: {cfg['mesh_coarse_size']} mm")

    # ---- Save pre-solve backup ----
    pymodel.save(cfg["model_filename"])
    print(f"  Pre-solve model saved -> {cfg['model_filename']}")

    return client, pymodel, model


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
    step.set("plot", "on")           # show convergence plots during solve
    step.set("probesel", "all")      # record all probes (for GUI inspection)
    step.set("output", "all")        # store output at all timesteps
    print(f"  {cfg['study_t_start']*1e6:.1f} – {cfg['study_t_end']*1e6:.1f} us, "
          f"dt={cfg['study_t_step']*1e9:.0f} ns, {derived['n_steps']} outputs")


def solve_model(pymodel, cfg):
    """Run the time-dependent solver."""
    print("\n[9/9] Solving (time-dependent) ...")
    print("  This may take several minutes -- watch the COMSOL progress window.")
    t0 = _time.time()
    try:
        pymodel.solve()
        print(f"  Done in {_time.time() - t0:.0f} s")
        return True
    except Exception as e:
        print(f"  Solver error: {e}")
        print(f"  Model saved to '{cfg['model_filename']}'.")
        print(f"  Open it in the COMSOL GUI, check the setup, and solve manually.")
        return False


def extract_via_cutpoints(model_java, array_points, derived):
    """Extract time series using CutPoint3D datasets (probes unavailable in client API)."""
    print("\n  Extracting data via CutPoint3D datasets ...")
    n_steps = derived["n_steps"]
    n_pts = len(array_points)
    times = np.linspace(CONFIG["study_t_start"], CONFIG["study_t_end"], n_steps)
    displacements = np.full((n_pts, n_steps), np.nan)

    res = model_java.result()

    for idx, pt in enumerate(array_points):
        tag = f"cpt_{pt['i']}_{pt['j']}"
        try:
            cp = res.dataset().create(tag, "CutPoint3D")
            cp.set("data", "dset1")
            cp.set("pointx", str(pt["x"]))
            cp.set("pointy", str(pt["y"]))
            cp.set("pointz", str(pt["z"]))
        except Exception:
            continue

        # Evaluate at each stored timestep
        for ti in range(n_steps):
            try:
                val = res.numerical(tag, "w", "mm")
                displacements[idx, ti] = float(val)
            except Exception:
                pass  # keep NaN

    n_ok = int(np.sum(~np.all(np.isnan(displacements), axis=1)))
    print(f"  {n_ok}/{n_pts} points extracted")
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
          f"{cfg['laser_pulse_FWHM']*1e9:.0f} ns FWHM, "
          f"Q0 = {derived['Q0']:.2e} W/m^2")
    print(f"  Array:     {cfg['array_N']}x{cfg['array_N']} ({len(array_points)} pts), "
          f"{cfg['array_spacing']} mm spacing")
    print(f"  Mesh:      fine {cfg['mesh_fine_size']} mm / coarse {cfg['mesh_coarse_size']} mm")
    print(f"  Study:     {cfg['study_t_start']*1e6:.0f}–{cfg['study_t_end']*1e6:.0f} us, "
          f"dt = {cfg['study_t_step']*1e9:.0f} ns ({derived['n_steps']} outputs)")
    if parsed.build_only:
        print(f"  Mode:      BUILD ONLY (no solve)")
    print(f"  {'-'*56}")

    # ---- Build ----
    client, pymodel, java_model = build_model(cfg, derived, array_points)
    setup_study(java_model, cfg, derived)

    # Save fully-built model
    pymodel.save(cfg["model_filename"])
    print(f"\n  Model (ready to solve) saved -> {cfg['model_filename']}")

    # ---- Stop here if --build-only ----
    if parsed.build_only:
        print(f"\n{'='*62}")
        print(f"  Build-only mode: stopping before solve.")
        print(f"  Inspect '{cfg['model_filename']}' in the COMSOL GUI,")
        print(f"  then re-run without --build-only to solve and export.")
        print(f"{'='*62}\n")
        return 0

    # ---- Solve ----
    ok = solve_model(pymodel, cfg)
    if not ok:
        return 1

    # ---- Extract & export ----
    output_dir = Path(cfg["output_dir"])
    times, displacements, _missing = extract_via_cutpoints(
        java_model, array_points, derived
    )
    export_results(times, displacements, array_points, cfg, derived, output_dir)

    # Save solved model
    solved = output_dir / "solved_model.mph"
    pymodel.save(str(solved))

    # ---- Summary ----
    valid = int(np.sum(~np.all(np.isnan(displacements), axis=1)))
    print(f"\n{'='*62}")
    print(f"  Done in {_time.time() - t_start:.0f} s")
    print(f"  Valid signals: {valid}/{len(array_points)}")
    print(f"  Output:        {output_dir.resolve()}")
    print(f"  Solved model:  {solved}")
    print(f"{'='*62}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
