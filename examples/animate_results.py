#!/usr/bin/env python3
"""
Generate a wave-propagation animation from a solved COMSOL model.

Loads a solved .mph file, extracts the top-surface z-displacement field
at each timestep, and renders an MP4 animation showing guided-wave propagation.

Usage:
  python animate_results.py [path/to/solved_model.mph]
"""

import mph
import numpy as np
from pathlib import Path
import sys
import argparse
from datetime import datetime


def load_surface_field(model, timesteps=None):
    """Extract z-displacement (w) and coordinates on the top surface (z = Lz)."""
    print("Extracting displacement field on top surface ...")

    # Get all coordinates and displacement
    x = model.evaluate("x", "mm")
    y = model.evaluate("y", "mm")
    z = model.evaluate("z", "mm")
    w = model.evaluate("w", "mm")

    n_steps, n_nodes = w.shape
    print(f"  Field shape: {n_steps} timesteps x {n_nodes} nodes")

    # Use z at t=0 (undeformed mesh) to find top-surface nodes
    z0 = z[0]  # (n_nodes,) — undeformed z-coordinates
    z_max = np.max(z0)
    mask = np.abs(z0 - z_max) < 1e-4
    n_surface = np.sum(mask)
    print(f"  Surface nodes: {n_surface}")

    # Extract surface coordinates and displacement
    xs = x[0, mask]
    ys = y[0, mask]
    ws = w[:, mask]  # (n_steps, n_surface)

    # Sort by position for consistent heatmap rendering
    # Create a regular grid via interpolation
    return xs, ys, ws, n_steps


def make_animation(xs, ys, ws, n_steps, output_path, times_s, fps=15):
    """Create MP4 animation of the surface displacement field."""
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    from scipy.interpolate import griddata

    print("Interpolating onto regular grid ...")
    # Create regular grid covering the surface
    grid_n = 100
    xi = np.linspace(xs.min(), xs.max(), grid_n)
    yi = np.linspace(ys.min(), ys.max(), grid_n)
    XI, YI = np.meshgrid(xi, yi)

    # Determine global color limits
    w_max = np.nanmax(np.abs(ws))
    if w_max < 1e-15:
        print("  WARNING: All displacements are zero — nothing to animate.")
        return
    vlim = w_max * 0.7  # clip to 70% for better contrast

    print(f"  Grid: {grid_n}x{grid_n}, max |w| = {w_max:.3e} mm")
    print(f"  Rendering {n_steps} frames at {fps} fps ...")

    # Interpolate all timesteps onto the grid
    frames = []
    step = max(1, n_steps // 200)  # limit to ~200 frames for performance
    for ti in range(0, n_steps, step):
        zi = griddata((xs, ys), ws[ti], (XI, YI), method="linear", fill_value=0)
        frames.append(zi)

    n_frames = len(frames)
    print(f"  {n_frames} frames to render")

    # Create animation
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(
        frames[0],
        origin="lower",
        extent=[xs.min(), xs.max(), ys.min(), ys.max()],
        cmap="seismic",
        vmin=-vlim,
        vmax=vlim,
        interpolation="bilinear",
    )
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    ax.set_aspect("equal")

    # Mark laser source position (center)
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    ax.plot(cx, cy, "k*", markersize=8, label="Laser source")
    ax.legend(loc="upper right", fontsize=8)

    cbar = plt.colorbar(im, ax=ax, label="w (mm)")
    title = ax.set_title("")

    def update(frame_idx):
        im.set_array(frames[frame_idx])
        t_us = frame_idx * step * (times_s[1] - times_s[0] if len(times_s) > 1 else 1e-8) * 1e6
        title.set_text(f"t = {t_us:.3f} us")
        return [im, title]

    ani = animation.FuncAnimation(
        fig, update, frames=n_frames, interval=1000 / fps, blit=True
    )

    # Save — try MP4 first, fall back to GIF
    try:
        writer = animation.FFMpegWriter(fps=fps, bitrate=2000)
        out_path = Path(str(output_path).replace(".mp4", "") + ".mp4")
        ani.save(str(out_path), writer=writer)
    except (FileNotFoundError, OSError):
        print("  ffmpeg not found, saving as GIF instead ...")
        out_path = Path(str(output_path).replace(".mp4", "") + ".gif")
        ani.save(str(out_path), writer="pillow", fps=fps)
    plt.close(fig)

    print(f"  Animation saved -> {out_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate wave-propagation animation from solved COMSOL model"
    )
    parser.add_argument(
        "model", nargs="?", default="output/solved_model.mph",
        help="Path to solved .mph file (default: output/solved_model.mph)"
    )
    parser.add_argument(
        "--fps", type=int, default=15,
        help="Frames per second (default: 15)"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output path (default: <model_dir>/wave_animation.mp4)"
    )
    args = parser.parse_args()

    model_path = Path(args.model)
    if not model_path.exists():
        print(f"Error: model not found: {model_path}")
        print("Run laser_ultrasound_model.py first to generate the solved model.")
        return 1

    output_path = args.output
    if output_path is None:
        output_path = model_path.parent / "wave_animation.mp4"
    else:
        output_path = Path(output_path)

    print(f"Loading: {model_path}")
    mph.option("session", "stand-alone")
    client = mph.start(cores=2)
    model = client.load(str(model_path))

    xs, ys, ws, n_steps = load_surface_field(model)

    # Time array: evaluate t at first node (same for all nodes)
    t_raw = model.evaluate("t", "s")
    times = t_raw if t_raw.ndim == 1 else t_raw[:, 0]

    make_animation(xs, ys, ws, n_steps, output_path, times, fps=args.fps)

    print("Done!")
    return 0


if __name__ == "__main__":
    import matplotlib
    matplotlib.use("Agg")
    sys.exit(main())
