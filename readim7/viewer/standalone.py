"""
High-performance standalone OpenGL viewer for DaVis streams, images, and vector fields using Dear PyGui.
"""
import argparse
import sys
import time
from pathlib import Path
import numpy as np

try:
    import dearpygui.dearpygui as dpg
except ImportError:
    dpg = None

from .loader import open_dataset, BaseDataSource
from .colormaps import apply_colormap_rgba, AVAILABLE_COLORMAPS


class StandaloneViewer:
    """Dear PyGui accelerated OpenGL DaVis viewer."""

    def __init__(self, dataset: BaseDataSource):
        if dpg is None:
            raise ImportError(
                "Dear PyGui is required for the standalone viewer. "
                "Install it via: pip install 'readim7[viewer]'"
            )
        self.dataset = dataset
        self.current_frame = getattr(dataset, "initial_idx", 0)
        self.current_channel = 0
        self.colormap = "gray"
        
        # Playback state
        self.is_playing = False
        self.target_fps = 30
        self.last_frame_time = time.perf_counter()

        # Dynamic contrast state
        self.vmin = 0.0
        self.vmax = 4095.0
        self._current_raw_frame = None

        # Texture and series tags
        self.tex_tag = "img_dynamic_texture"
        self.series_tag = "img_series_item"
        self.plot_tag = "main_plot"
        self.xaxis_tag = "plot_xaxis"
        self.yaxis_tag = "plot_yaxis"

    def _update_frame_data(self, reset_contrast=False):
        """Fetch active frame from dataset and update GPU texture."""
        self._current_raw_frame = self.dataset.get_frame(self.current_frame, self.current_channel)
        
        if reset_contrast:
            raw_min, raw_max, p1, p99 = self.dataset.get_stats(self.current_frame, self.current_channel)
            self.vmin = float(p1)
            self.vmax = float(p99 if p99 > p1 else raw_max)
            if dpg.does_item_exist("drag_vmin"):
                dpg.set_value("drag_vmin", self.vmin)
                dpg.set_value("drag_vmax", self.vmax)

        # Apply colormap and contrast windowing
        rgba = apply_colormap_rgba(self._current_raw_frame, self.vmin, self.vmax, self.colormap)
        
        # Update dynamic texture buffer on GPU
        if dpg.does_item_exist(self.tex_tag):
            dpg.set_value(self.tex_tag, rgba.reshape(-1))

        # Update frame info text
        if dpg.does_item_exist("txt_frame_info"):
            dpg.set_value(
                "txt_frame_info",
                f"Frame: {self.current_frame + 1}/{self.dataset.num_frames} | "
                f"Resolution: {self.dataset.nx}x{self.dataset.ny} | "
                f"Raw Range: [{self._current_raw_frame.min():.1f}, {self._current_raw_frame.max():.1f}]"
            )

    def _setup_texture(self):
        """Register or recreate dynamic texture for current dataset dimensions."""
        if dpg.does_item_exist(self.tex_tag):
            dpg.delete_item(self.tex_tag)
        if dpg.does_item_exist(self.series_tag):
            dpg.delete_item(self.series_tag)

        # Allocate empty texture
        blank = np.zeros((self.dataset.ny, self.dataset.nx, 4), dtype=np.float32)
        with dpg.texture_registry(show=False):
            dpg.add_dynamic_texture(
                width=self.dataset.nx,
                height=self.dataset.ny,
                default_value=blank.reshape(-1),
                tag=self.tex_tag,
            )

        if dpg.does_item_exist(self.yaxis_tag):
            dpg.add_image_series(
                self.tex_tag,
                bounds_min=[0, self.dataset.ny],
                bounds_max=[self.dataset.nx, 0],
                tag=self.series_tag,
                parent=self.yaxis_tag,
            )
            self.reset_view()

    def reset_view(self):
        """Fit image to plot viewport."""
        if dpg.does_item_exist(self.xaxis_tag) and dpg.does_item_exist(self.yaxis_tag):
            dpg.set_axis_limits(self.xaxis_tag, 0, self.dataset.nx)
            dpg.set_axis_limits(self.yaxis_tag, self.dataset.ny, 0)

    def load_dataset(self, new_dataset: BaseDataSource):
        """Load a new dataset in-place."""
        self.dataset = new_dataset
        self.current_frame = getattr(new_dataset, "initial_idx", 0)
        self.current_channel = 0
        
        # Update UI components
        dpg.configure_item(
            "slider_frame",
            max_value=max(0, self.dataset.num_frames - 1),
            default_value=self.current_frame,
        )
        dpg.configure_item(
            "combo_channel",
            items=self.dataset.channels,
            default_value=self.dataset.channels[0],
        )
        dpg.set_value("txt_title", f"File: {self.dataset.title}")
        
        self._setup_texture()
        self._update_frame_data(reset_contrast=True)

    def setup_ui(self):
        """Construct Dear PyGui window layout and textures."""
        dpg.create_context()
        dpg.create_viewport(
            title=f"readim7 viewer - {self.dataset.title}",
            width=1200,
            height=850,
            min_width=800,
            min_height=600,
        )

        # File Dialog
        def _on_file_select(sender, app_data):
            selections = app_data.get("selections")
            if selections:
                selected_path = list(selections.values())[0]
            else:
                selected_path = app_data.get("file_path_name")
            if selected_path:
                try:
                    ds = open_dataset(selected_path)
                    self.load_dataset(ds)
                except Exception as ex:
                    print(f"Error opening {selected_path}: {ex}", file=sys.stderr)

        with dpg.file_dialog(
            directory_selector=False,
            show=False,
            callback=_on_file_select,
            tag="file_dialog",
            width=700,
            height=450,
        ):
            dpg.add_file_extension(".*", color=(150, 150, 150, 255))
            dpg.add_file_extension(".ims", color=(100, 255, 100, 255))
            dpg.add_file_extension(".im7", color=(100, 200, 255, 255))
            dpg.add_file_extension(".vc7", color=(255, 200, 100, 255))

        # Main Layout Window
        with dpg.window(tag="main_window", no_title_bar=True):
            # Top Controls Row 1: File & Channel & Colormap
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Open File...",
                    callback=lambda: dpg.show_item("file_dialog"),
                )
                dpg.add_text(f"File: {self.dataset.title}", tag="txt_title")
                dpg.add_spacer(width=20)
                dpg.add_text("Channel:")
                def _on_channel(sender, value):
                    idx = self.dataset.channels.index(value) if value in self.dataset.channels else 0
                    self.current_channel = idx
                    self._update_frame_data(reset_contrast=False)
                dpg.add_combo(
                    items=self.dataset.channels,
                    default_value=self.dataset.channels[0],
                    tag="combo_channel",
                    callback=_on_channel,
                    width=180,
                )
                dpg.add_text("Colormap:")
                def _on_cmap(sender, value):
                    self.colormap = value
                    self._update_frame_data(reset_contrast=False)
                dpg.add_combo(
                    items=AVAILABLE_COLORMAPS,
                    default_value=self.colormap,
                    tag="combo_colormap",
                    callback=_on_cmap,
                    width=100,
                )
                dpg.add_button(label="Reset View", callback=self.reset_view)

            # Top Controls Row 2: Playback & Scrubbing
            with dpg.group(horizontal=True):
                def _step_prev():
                    if self.current_frame > 0:
                        self.current_frame -= 1
                        dpg.set_value("slider_frame", self.current_frame)
                        self._update_frame_data(reset_contrast=False)

                def _step_next():
                    if self.current_frame < self.dataset.num_frames - 1:
                        self.current_frame += 1
                        dpg.set_value("slider_frame", self.current_frame)
                        self._update_frame_data(reset_contrast=False)

                def _toggle_play():
                    self.is_playing = not self.is_playing
                    dpg.configure_item("btn_play", label="Pause" if self.is_playing else "Play")

                dpg.add_button(label="|<", callback=lambda: self._set_frame(0))
                dpg.add_button(label="<", callback=_step_prev)
                dpg.add_button(label="Play", tag="btn_play", callback=_toggle_play, width=60)
                dpg.add_button(label=">", callback=_step_next)
                dpg.add_button(label=">|", callback=lambda: self._set_frame(self.dataset.num_frames - 1))

                def _on_scrub(sender, value):
                    self.current_frame = int(value)
                    self._update_frame_data(reset_contrast=False)

                dpg.add_slider_int(
                    min_value=0,
                    max_value=max(0, self.dataset.num_frames - 1),
                    default_value=self.current_frame,
                    tag="slider_frame",
                    callback=_on_scrub,
                    width=350,
                )
                dpg.add_text("FPS:")
                def _on_fps(sender, value):
                    self.target_fps = int(value)
                dpg.add_slider_int(
                    min_value=1,
                    max_value=60,
                    default_value=self.target_fps,
                    tag="slider_fps",
                    callback=_on_fps,
                    width=100,
                )

            # Top Controls Row 3: Contrast windowing
            with dpg.group(horizontal=True):
                def _auto_contrast():
                    self._update_frame_data(reset_contrast=True)

                dpg.add_button(label="Auto Contrast", callback=_auto_contrast)
                dpg.add_text("Min:")
                def _on_min(sender, value):
                    self.vmin = float(value)
                    self._update_frame_data(reset_contrast=False)
                dpg.add_drag_float(
                    default_value=self.vmin,
                    tag="drag_vmin",
                    callback=_on_min,
                    width=100,
                    speed=2.0,
                )
                dpg.add_text("Max:")
                def _on_max(sender, value):
                    self.vmax = float(value)
                    self._update_frame_data(reset_contrast=False)
                dpg.add_drag_float(
                    default_value=self.vmax,
                    tag="drag_vmax",
                    callback=_on_max,
                    width=100,
                    speed=2.0,
                )
                dpg.add_text("", tag="txt_frame_info")

            # Main Viewport Plot
            with dpg.plot(
                tag=self.plot_tag,
                height=-30,
                width=-1,
                equal_aspects=True,
                no_title=True,
            ):
                dpg.add_plot_axis(dpg.mvXAxis, label="X [pixels]", tag=self.xaxis_tag)
                dpg.add_plot_axis(dpg.mvYAxis, label="Y [pixels]", tag=self.yaxis_tag)

            # Bottom Status Bar / Pixel probe
            dpg.add_text(
                "Controls: [Space] Play/Pause | [Left/Right] Step | [A/B] Pulse | [C] Auto Contrast | [R] Reset View | Scroll to Zoom, Drag to Pan",
                tag="txt_status",
            )

        # Keyboard shortcuts handler
        with dpg.handler_registry():
            def _on_key(sender, app_data):
                # Spacebar
                if app_data == 32:
                    _toggle_play()
                # Left arrow
                elif app_data == 263:
                    _step_prev()
                # Right arrow
                elif app_data == 262:
                    _step_next()
                # 'A'
                elif app_data == 65 and len(self.dataset.channels) > 0:
                    self.current_channel = 0
                    dpg.set_value("combo_channel", self.dataset.channels[0])
                    self._update_frame_data(reset_contrast=False)
                # 'B'
                elif app_data == 66 and len(self.dataset.channels) > 1:
                    self.current_channel = 1
                    dpg.set_value("combo_channel", self.dataset.channels[1])
                    self._update_frame_data(reset_contrast=False)
                # 'C'
                elif app_data == 67:
                    _auto_contrast()
                # 'R'
                elif app_data == 82:
                    self.reset_view()

            dpg.add_key_press_handler(callback=_on_key)

        dpg.setup_dearpygui()
        dpg.set_primary_window("main_window", True)
        
        self._setup_texture()
        self._update_frame_data(reset_contrast=True)

    def run(self):
        """Launch the viewer window and run event loop."""
        self.setup_ui()
        dpg.show_viewport()

        # Render loop with smooth playback
        while dpg.is_dearpygui_running():
            now = time.perf_counter()
            if self.is_playing and (now - self.last_frame_time) >= (1.0 / self.target_fps):
                self.last_frame_time = now
                if self.current_frame < self.dataset.num_frames - 1:
                    self.current_frame += 1
                else:
                    self.current_frame = 0
                dpg.set_value("slider_frame", self.current_frame)
                self._update_frame_data(reset_contrast=False)
            dpg.render_dearpygui_frame()

        dpg.destroy_context()

    def _set_frame(self, frame_idx):
        self.current_frame = max(0, min(frame_idx, self.dataset.num_frames - 1))
        dpg.set_value("slider_frame", self.current_frame)
        self._update_frame_data(reset_contrast=False)


def launch_standalone(path=None):
    """Entry point to launch the standalone OpenGL viewer."""
    dataset = open_dataset(path)
    viewer = StandaloneViewer(dataset)
    viewer.run()


def main():
    parser = argparse.ArgumentParser(
        description="readim7 ultra-fast standalone DaVis file & stream viewer"
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to .ims stream, .im7 image, .vc7 vector file, or folder",
    )
    args = parser.parse_args()
    try:
        launch_standalone(args.path)
    except Exception as e:
        print(f"Error launching viewer: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
