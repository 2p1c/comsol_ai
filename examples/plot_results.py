#!/usr/bin/env python3
"""
Visualization for laser-ultrasound simulation results.

Reads output/laser_ultrasound_data.npz and generates:
  1. Time-series overlaid plot — all array points
  2. Individual time-series plots per point
  3. 2D amplitude map (peak-to-peak) of the array
  4. Wavefield snapshot plot at selected times

Usage:
  python plot_results.py [path/to/laser_ultrasound_data.npz]
"""

import numpy as np
from pathlib import Path
import sys
import json
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec


def load_data(npz_path):
    """Load simulation results from .npz file."""
    data = np.load(npz_path, allow_pickle=True)
    times = data["times"]                    # (n_steps,)
    displacements = data["displacements"]     # (n_points, n_steps)
    array_coords = data["array_coords"]       # (n_points, 3)
    array_labels = data["array_labels"]       # (n_points,)
    try:
        config = json.loads(str(data["config_json"]))
    except (KeyError, json.JSONDecodeError):
        config = {}

    print(f"Loaded: {displacements.shape[0]} points x "
          f"{displacements.shape[1]} time steps")
    print(f"Time range: {times[0]*1e6:.2f} – {times[-1]*1e6:.2f} us")
    return times, displacements, array_coords, array_labels, config


def plot_overlay(times, displacements, array_labels, output_dir):
    """Overlaid time-series for all array points."""
    fig, ax = plt.subplots(figsize=(14, 6))

    n_pts = displacements.shape[0]
    cmap = plt.cm.viridis(np.linspace(0, 1, n_pts))

    for idx in range(n_pts):
        w = displacements[idx]
        valid = ~np.isnan(w)
        if valid.any():
            ax.plot(times[valid] * 1e6, w[valid] * 1e3,
                    color=cmap[idx], alpha=0.7, linewidth=0.5,
                    label=array_labels[idx] if idx % max(1, n_pts // 10) == 0 else None)

    ax.set_xlabel("Time (us)", fontsize=12)
    ax.set_ylabel("z-displacement w (um)", fontsize=12)
    ax.set_title(f"Laser-Ultrasound Signals — {n_pts} Array Points", fontsize=14)
    if n_pts <= 50:
        ax.legend(fontsize=7, ncol=2, loc="upper right")
    ax.grid(True, alpha=0.3)

    path = output_dir / "overlay_timeseries.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  -> {path}")


def plot_individual(times, displacements, array_labels, array_coords, output_dir):
    """Individual time-series subplots in a grid matching the array layout."""
    n_pts = displacements.shape[0]
    # Determine grid dimensions from unique x, y coordinates
    unique_x = np.unique(array_coords[:, 0])
    unique_y = np.unique(array_coords[:, 1])
    n_rows = len(unique_y)
    n_cols = len(unique_x)

    fig, axes = plt.subplots(n_rows, n_cols,
                             figsize=(n_cols * 2, n_rows * 1.6),
                             sharex=True, sharey=True)
    fig.suptitle("Individual Array Point Signals", fontsize=14)

    # Map (x,y) to subplot position
    x_to_col = {x: i for i, x in enumerate(sorted(unique_x))}
    y_to_row = {y: n_rows - 1 - i for i, y in enumerate(sorted(unique_y))}

    for idx in range(n_pts):
        x, y = array_coords[idx, 0], array_coords[idx, 1]
        row, col = y_to_row[y], x_to_col[x]
        ax = axes[row, col] if n_rows > 1 or n_cols > 1 else axes

        w = displacements[idx]
        valid = ~np.isnan(w)
        if valid.any():
            ax.plot(times[valid] * 1e6, w[valid] * 1e3, linewidth=0.6, color="steelblue")

        ax.set_title(array_labels[idx], fontsize=7)
        ax.tick_params(labelsize=6)
        ax.grid(True, alpha=0.2)

    # Global labels
    for ax in axes.flat if hasattr(axes, "flat") else [axes]:
        pass

    fig.text(0.5, 0.02, "Time (us)", ha="center", fontsize=11)
    fig.text(0.02, 0.5, "w (um)", va="center", rotation="vertical", fontsize=11)

    plt.tight_layout()
    path = output_dir / "individual_timeseries.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  -> {path}")


def plot_amplitude_map(times, displacements, array_coords, array_labels, output_dir):
    """2D heatmap of peak-to-peak amplitude across the array."""
    n_pts = displacements.shape[0]
    unique_x = np.unique(array_coords[:, 0])
    unique_y = np.unique(array_coords[:, 1])
    nx, ny = len(unique_x), len(unique_y)

    # Compute peak-to-peak for each point
    p2p = np.zeros(n_pts)
    for idx in range(n_pts):
        w = displacements[idx]
        valid = ~np.isnan(w)
        if valid.any():
            p2p[idx] = np.ptp(w[valid])

    # Check if data is arranged as a regular grid
    dx = np.diff(sorted(unique_x))
    dy = np.diff(sorted(unique_y))
    regular_grid = np.allclose(dx, dx[0]) and np.allclose(dy, dy[0])

    fig, axes = plt.subplots(1, 2 if regular_grid else 1,
                             figsize=(14, 5) if regular_grid else (8, 6))
    if not regular_grid:
        axes = [axes]

    # Scatter plot (works for any arrangement)
    ax = axes[0]
    sc = ax.scatter(array_coords[:, 0], array_coords[:, 1],
                    c=p2p * 1e3, cmap="hot", s=80, edgecolors="k", linewidth=0.5)
    ax.set_xlabel("x (mm)", fontsize=12)
    ax.set_ylabel("y (mm)", fontsize=12)
    ax.set_title("Peak-to-Peak Amplitude", fontsize=13)
    ax.set_aspect("equal")
    cbar = plt.colorbar(sc, ax=ax)
    cbar.set_label("w_p2p (um)", fontsize=11)

    # Label the laser source position
    cx, cy = np.mean(unique_x), np.mean(unique_y)
    ax.plot(cx, cy, "r*", markersize=15, label="Laser source")
    ax.legend(fontsize=9)

    if regular_grid:
        # 2D image plot
        ax2 = axes[1]
        p2p_grid = p2p.reshape(ny, nx)
        extent = [
            unique_x[0] - dx[0] / 2,
            unique_x[-1] + dx[0] / 2,
            unique_y[0] - dy[0] / 2,
            unique_y[-1] + dy[0] / 2,
        ]
        im = ax2.imshow(p2p_grid * 1e3, origin="lower", extent=extent,
                        aspect="equal", cmap="hot")
        ax2.set_xlabel("x (mm)", fontsize=12)
        ax2.set_ylabel("y (mm)", fontsize=12)
        ax2.set_title("Amplitude Map (Interpolated)", fontsize=13)
        cbar2 = plt.colorbar(im, ax=ax2)
        cbar2.set_label("w_p2p (um)", fontsize=11)

    plt.tight_layout()
    path = output_dir / "amplitude_map.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  -> {path}")


def plot_Bscan(times, displacements, array_coords, array_labels, output_dir):
    """B-scan plot: time vs. distance along the center line of the array."""
    # Find points along the center line (y = cy, varying x)
    unique_y = np.unique(array_coords[:, 1])
    cy = np.median(unique_y)

    # Select points closest to y = cy
    center_indices = []
    for idx in range(len(array_labels)):
        if abs(array_coords[idx, 1] - cy) < 1e-6:
            center_indices.append(idx)

    if len(center_indices) < 2:
        print("  (B-scan skipped: need >=2 points along center line)")
        return

    # Sort by x
    center_indices.sort(key=lambda i: array_coords[i, 0])
    x_vals = np.array([array_coords[i, 0] for i in center_indices])

    # Build B-scan matrix
    n_x = len(center_indices)
    n_t = len(times)
    bscan = np.zeros((n_x, n_t))
    for i, idx in enumerate(center_indices):
        w = displacements[idx]
        bscan[i, :] = np.where(np.isnan(w), 0, w)

    fig, ax = plt.subplots(figsize=(12, 5))
    extent = [times[0] * 1e6, times[-1] * 1e6, x_vals[0], x_vals[-1]]
    im = ax.imshow(bscan * 1e3, aspect="auto", origin="lower", extent=extent,
                   cmap="seismic", vmin=-np.max(np.abs(bscan)) * 1e3 * 0.5,
                   vmax=np.max(np.abs(bscan)) * 1e3 * 0.5)

    ax.set_xlabel("Time (us)", fontsize=12)
    ax.set_ylabel("x position (mm)", fontsize=12)
    ax.set_title("B-Scan: Center Line (y = {:.1f} mm)".format(cy), fontsize=13)
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label("w (um)", fontsize=11)

    plt.tight_layout()
    path = output_dir / "bscan.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  -> {path}")


def plot_wavefield_snapshots(times, displacements, array_coords, output_dir):
    """Snapshots of the displacement field at several time instants."""
    n_pts = displacements.shape[0]
    n_steps = len(times)
    unique_x = np.unique(array_coords[:, 0])
    unique_y = np.unique(array_coords[:, 1])
    nx, ny = len(unique_x), len(unique_y)

    # Check if data is regular grid
    dx = np.diff(sorted(unique_x))
    dy = np.diff(sorted(unique_y))
    if not (np.allclose(dx, dx[0]) and np.allclose(dy, dy[0])):
        print("  (Wavefield snapshots skipped: irregular grid)")
        return

    # Choose 4 snapshot times
    t_indices = np.linspace(0, n_steps - 1, 4, dtype=int)

    fig, axes = plt.subplots(1, 4, figsize=(18, 4.5))
    extent = [
        unique_x[0] - dx[0] / 2, unique_x[-1] + dx[0] / 2,
        unique_y[0] - dy[0] / 2, unique_y[-1] + dy[0] / 2,
    ]

    global_max = np.nanmax(np.abs(displacements))

    for k, t_idx in enumerate(t_indices):
        ax = axes[k]
        w_snapshot = displacements[:, t_idx].reshape(ny, nx) * 1e3  # um
        im = ax.imshow(w_snapshot, origin="lower", extent=extent,
                       aspect="equal", cmap="seismic",
                       vmin=-global_max * 1e3 * 0.7, vmax=global_max * 1e3 * 0.7)
        ax.set_title(f"t = {times[t_idx]*1e6:.2f} us", fontsize=10)
        ax.set_xlabel("x (mm)", fontsize=9)
        ax.set_ylabel("y (mm)", fontsize=9)
        plt.colorbar(im, ax=ax, label="w (um)")

    fig.suptitle("Wavefield Snapshots", fontsize=14, y=1.02)
    plt.tight_layout()
    path = output_dir / "wavefield_snapshots.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  -> {path}")


def main():
    # Find input file
    if len(sys.argv) > 1:
        npz_path = Path(sys.argv[1])
    else:
        npz_path = Path("output/laser_ultrasound_data.npz")

    if not npz_path.exists():
        print(f"Error: file not found: {npz_path}")
        print("Run laser_ultrasound_model.py first to generate data.")
        return 1

    output_dir = npz_path.parent / "plots"
    output_dir.mkdir(exist_ok=True)

    print(f"Reading: {npz_path}")
    times, displacements, coords, labels, config = load_data(npz_path)
    print(f"Writing plots to: {output_dir}\n")

    plot_overlay(times, displacements, labels, output_dir)
    plot_amplitude_map(times, displacements, coords, labels, output_dir)
    plot_Bscan(times, displacements, coords, labels, output_dir)

    # Individual plots only for small arrays
    n_pts = displacements.shape[0]
    if n_pts <= 100:
        plot_individual(times, displacements, labels, coords, output_dir)

    plot_wavefield_snapshots(times, displacements, coords, output_dir)

    print(f"\nDone! {len(list(output_dir.glob('*.png')))} plots saved to {output_dir}")
    return 0


if __name__ == "__main__":
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend
    sys.exit(main())
