import marimo

__generated_with = "0.25.0"
app = marimo.App(width="full")


@app.cell
def __():
    import sys
    from pathlib import Path
    import numpy as np
    from PIL import Image
    import marimo as mo

    from readim7.viewer.loader import open_dataset, BaseDataSource
    from readim7.viewer.colormaps import apply_colormap_rgb8, AVAILABLE_COLORMAPS
    from readim7.extra import get_sample_image_filenames
    return (
        AVAILABLE_COLORMAPS,
        BaseDataSource,
        Image,
        Path,
        apply_colormap_rgb8,
        get_sample_image_filenames,
        mo,
        np,
        open_dataset,
        sys,
    )


@app.cell
def __(mo, sys):
    # Detect path from command line arguments or default sample
    args = mo.cli_args()
    initial_path = ""
    if args:
        # Check positional args or --path
        if "path" in args:
            initial_path = str(args["path"])
        elif len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
            initial_path = sys.argv[1]

    path_input = mo.ui.text(
        value=initial_path,
        placeholder="Enter path to .ims, .im7, .vc7, or folder...",
        label="Dataset Path",
        full_width=True,
    )
    return args, initial_path, path_input


@app.cell
def __(mo, path_input):
    header = mo.md(
        f"""
        # 🔬 readim7 Reactive Viewer
        Inspect high-speed DaVis stream (`.ims`), image (`.im7`), and vector (`.vc7`) files with live scrubbing.
        """
    )
    mo.vstack([header, path_input])
    return (header,)


@app.cell
def __(mo, open_dataset, path_input):
    active_path = path_input.value.strip() or None
    error_msg = None
    dataset = None
    try:
        dataset = open_dataset(active_path)
    except Exception as e:
        error_msg = f"Failed to load dataset: {e}"

    if error_msg:
        mo.output.replace(mo.callout(error_msg, kind="danger"))
    return active_path, dataset, error_msg


@app.cell
def __(AVAILABLE_COLORMAPS, dataset, mo):
    mo.stop(dataset is None)

    # Frame & playback controls
    slider_frame = mo.ui.slider(
        start=0,
        stop=max(0, dataset.num_frames - 1),
        value=getattr(dataset, "initial_idx", 0),
        step=1,
        label=f"Frame (0 to {dataset.num_frames - 1})",
        show_value=True,
        full_width=True,
    )

    channel_dropdown = mo.ui.dropdown(
        options=dataset.channels,
        value=dataset.channels[0],
        label="Channel / Pulse",
    )

    cmap_dropdown = mo.ui.dropdown(
        options=AVAILABLE_COLORMAPS,
        value="gray",
        label="Colormap",
    )

    scale_radio = mo.ui.radio(
        options=["100%", "50%", "25%"],
        value="100%",
        label="Display Scale",
        inline=True,
    )
    return channel_dropdown, cmap_dropdown, scale_radio, slider_frame


@app.cell
def __(channel_dropdown, dataset, slider_frame):
    # Compute frame statistics for contrast scaling
    ch_idx = (
        dataset.channels.index(channel_dropdown.value)
        if channel_dropdown.value in dataset.channels
        else 0
    )
    raw_min, raw_max, p1, p99 = dataset.get_stats(slider_frame.value, ch_idx)
    return ch_idx, p1, p99, raw_max, raw_min


@app.cell
def __(mo, p1, p99, raw_max, raw_min):
    contrast_slider = mo.ui.range_slider(
        start=float(raw_min),
        stop=float(max(raw_min + 1.0, raw_max)),
        value=[float(p1), float(p99 if p99 > p1 else raw_max)],
        label="Contrast Window [Min, Max]",
        full_width=True,
    )
    return (contrast_slider,)


@app.cell
def __(
    apply_colormap_rgb8,
    ch_idx,
    cmap_dropdown,
    contrast_slider,
    dataset,
    scale_radio,
    slider_frame,
):
    # Retrieve raw frame
    raw_frame = dataset.get_frame(slider_frame.value, ch_idx)

    # Apply downsampling if requested for maximum responsiveness
    scale_val = scale_radio.value
    if scale_val == "50%":
        work_frame = raw_frame[::2, ::2]
    elif scale_val == "25%":
        work_frame = raw_frame[::4, ::4]
    else:
        work_frame = raw_frame

    # Contrast windowing and colormap LUT
    vmin, vmax = contrast_slider.value
    rgb_arr = apply_colormap_rgb8(work_frame, vmin, vmax, cmap_dropdown.value)
    return raw_frame, rgb_arr, scale_val, vmin, vmax, work_frame


@app.cell
def __(Image, mo, rgb_arr, slider_frame, vmin, vmax):
    pil_img = Image.fromarray(rgb_arr)
    img_element = mo.image(
        pil_img,
        caption=f"Frame {slider_frame.value + 1} | Contrast: [{vmin:.1f}, {vmax:.1f}]",
        rounded=True,
    )
    return img_element, pil_img


@app.cell
def __(
    channel_dropdown,
    cmap_dropdown,
    contrast_slider,
    dataset,
    img_element,
    mo,
    raw_frame,
    scale_radio,
    slider_frame,
):
    # Assemble interactive layout
    controls_box = mo.hstack(
        [channel_dropdown, cmap_dropdown, scale_radio],
        justify="start",
        gap=2,
    )

    metadata_md = mo.md(
        f"""
        ### 📋 Dataset Info
        - **Source:** `{dataset.title}`
        - **Total Frames:** `{dataset.num_frames}`
        - **Resolution:** `{dataset.nx} × {dataset.ny}`
        - **Frame Value Range:** `[{raw_frame.min():.1f}, {raw_frame.max():.1f}]`
        """
    )

    main_view = mo.vstack([
        controls_box,
        slider_frame,
        contrast_slider,
        mo.hstack([img_element], justify="center"),
        mo.accordion({"Dataset Metadata": metadata_md}),
    ])
    main_view
    return controls_box, main_view, metadata_md


def launch_marimo(path=None):
    """Launch the reactive viewer via marimo CLI."""
    import subprocess
    import sys
    from pathlib import Path

    app_path = Path(__file__).resolve()
    cmd = [sys.executable, "-m", "marimo", "run", str(app_path)]
    if path:
        cmd.extend(["--", "--path", str(path)])
    
    print(f"Starting Marimo reactive viewer for: {path or 'default sample'}")
    subprocess.run(cmd)


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="readim7 Marimo reactive DaVis stream & image viewer"
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to .ims stream, .im7 image, .vc7 vector file, or folder",
    )
    args = parser.parse_args()
    try:
        launch_marimo(args.path)
    except Exception as e:
        print(f"Error launching Marimo viewer: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    app.run()
