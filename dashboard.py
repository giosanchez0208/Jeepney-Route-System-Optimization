"""
dashboard.py

Modernized Tkinter interactive dashboard for optimization diagnostics.
Added navigation buttons for generation switching.
"""

import json
import glob
import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
from PIL import ImageGrab, ImageTk, Image
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from utils.visualizer import StaticVisualizer

class MockNode:
    def __init__(self, lat, lon):
        self.lat = lat
        self.lon = lon

class MockEdge:
    def __init__(self, start, end):
        self.start = start
        self.end = end

class MockRoute:
    def __init__(self, path):
        self.path = path

class OptimizerDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Jeepney Route Optimization Dashboard")
        self.root.geometry("1450x850")
        
        self.colors = {
            "bg_main": "#f0f2f5",
            "bg_card": "#ffffff",
            "text_main": "#1c1e21",
            "text_muted": "#65676b",
            "accent": "#0078d4",
            "border": "#dadde1"
        }
        
        self.root.configure(bg=self.colors["bg_main"])
        self._setup_styles()
        self._load_data()
        self._init_ui()
        self.update_display()

    def _setup_styles(self):
        self.style = ttk.Style()
        if 'clam' in self.style.theme_names():
            self.style.theme_use('clam')

        self.style.configure('.', background=self.colors["bg_main"], foreground=self.colors["text_main"], font=('Segoe UI', 10))
        self.style.configure('Card.TFrame', background=self.colors["bg_card"])
        self.style.configure('Card.TLabel', background=self.colors["bg_card"], foreground=self.colors["text_main"])
        self.style.configure('Title.TLabel', background=self.colors["bg_card"], font=('Segoe UI', 16, 'bold'))
        self.style.configure('MetricLabel.TLabel', background=self.colors["bg_card"], font=('Segoe UI', 10), foreground=self.colors["text_muted"])
        self.style.configure('MetricValue.TLabel', background=self.colors["bg_card"], font=('Consolas', 14, 'bold'), foreground=self.colors["accent"])
        self.style.configure('TCheckbutton', background=self.colors["bg_card"], font=('Segoe UI', 10), padding=5)
        self.style.configure('TButton', font=('Segoe UI', 10), padding=4)
        self.style.configure('Nav.TButton', font=('Segoe UI', 10, 'bold'), width=3)
        self.style.map('TCheckbutton', background=[('active', self.colors["bg_card"])])

    def _load_data(self):
        runs = sorted(glob.glob("results/runs/opt_*"), reverse=True)
        if not runs: raise FileNotFoundError("No run directories found.")
        self.target_dir = Path(runs[0])
        
        files = sorted(self.target_dir.glob("snapshots/network_state_gen_*.json"), 
                       key=lambda x: int(x.stem.split('_')[-1]))
        if not files: raise FileNotFoundError("No JSON snapshots found.")

        self.snapshots = {}
        all_fit = []
        all_gap = []
        
        for f in files:
            with open(f, 'r') as file:
                data = json.load(file)
                self.snapshots[data["generation"]] = data
                all_fit.extend(data['distributions']['fitness'])
                all_gap.extend(data['distributions']['unserved_proxy'])

        self.generations = sorted(list(self.snapshots.keys()))
        self.current_gen = tk.IntVar(value=self.generations[0])

        if all_fit:
            self.fit_range = (min(all_fit), max(all_fit))
            fit_counts, _ = np.histogram(all_fit, bins=12, range=self.fit_range)
            self.max_y_fit = max(fit_counts) * 1.1
        else: 
            self.fit_range = (0, 1)
            self.max_y_fit = 10
        
        if all_gap:
            self.gap_range = (min(all_gap), max(all_gap))
            gap_counts, _ = np.histogram(all_gap, bins=12, range=self.gap_range)
            self.max_y_gap = max(gap_counts) * 1.1
        else: 
            self.gap_range = (0, 1)
            self.max_y_gap = 10

    def _init_ui(self):
        top_frame = tk.Frame(self.root, bg=self.colors["bg_card"], height=60)
        top_frame.pack(side=tk.TOP, fill=tk.X)
        top_frame.pack_propagate(False)
        tk.Frame(self.root, bg=self.colors["border"], height=1).pack(side=tk.TOP, fill=tk.X)

        header_inner = ttk.Frame(top_frame, style='Card.TFrame')
        header_inner.pack(side=tk.LEFT, fill=tk.BOTH, padx=20, pady=15)
        
        ttk.Label(header_inner, text="Optimization Run:", style='Card.TLabel', font=('Segoe UI', 12, 'bold')).pack(side=tk.LEFT)
        ttk.Label(header_inner, text=f"{self.target_dir.name}", style='Card.TLabel', foreground=self.colors["text_muted"], font=('Segoe UI', 12)).pack(side=tk.LEFT, padx=(5, 20))
        
        ttk.Label(header_inner, text="Generation:", style='Card.TLabel').pack(side=tk.LEFT, padx=10)
        
        # Navigation controls
        ttk.Button(header_inner, text="<", style='Nav.TButton', command=lambda: self._navigate_gen(-1)).pack(side=tk.LEFT, padx=2)
        self.gen_selector = ttk.Combobox(header_inner, textvariable=self.current_gen, values=self.generations, state="readonly", width=8)
        self.gen_selector.pack(side=tk.LEFT, padx=2)
        self.gen_selector.bind("<<ComboboxSelected>>", lambda e: self.update_display())
        ttk.Button(header_inner, text=">", style='Nav.TButton', command=lambda: self._navigate_gen(1)).pack(side=tk.LEFT, padx=2)

        content = ttk.Frame(self.root, padding=20)
        content.pack(fill=tk.BOTH, expand=True)
        
        left_card = tk.Frame(content, bg=self.colors["bg_card"], bd=1, relief="flat")
        left_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        ttk.Label(left_card, text="System Topology", style='Title.TLabel').pack(anchor=tk.W, padx=20, pady=(20, 5))
        
        self.map_label = ttk.Label(left_card, background=self.colors["bg_card"])
        self.map_label.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        footer = ttk.Frame(left_card, style='Card.TFrame')
        footer.pack(fill=tk.X, padx=20, pady=20)
        
        metrics_frame = ttk.Frame(footer, style='Card.TFrame')
        metrics_frame.pack(side=tk.LEFT)
        
        self.best_cost_var = tk.StringVar()
        self.mean_cost_var = tk.StringVar()
        
        m1 = ttk.Frame(metrics_frame, style='Card.TFrame')
        m1.pack(side=tk.LEFT, padx=(0, 20))
        ttk.Label(m1, text="Global Best Cost", style='MetricLabel.TLabel').pack(anchor=tk.W)
        ttk.Label(m1, textvariable=self.best_cost_var, style='MetricValue.TLabel').pack(anchor=tk.W)

        m2 = ttk.Frame(metrics_frame, style='Card.TFrame')
        m2.pack(side=tk.LEFT)
        ttk.Label(m2, text="Mean Population Cost", style='MetricLabel.TLabel').pack(anchor=tk.W)
        ttk.Label(m2, textvariable=self.mean_cost_var, style='MetricValue.TLabel').pack(anchor=tk.W)

        self.toggle_routes = tk.BooleanVar(value=True)
        self.toggle_phero = tk.BooleanVar(value=False)
        self.toggle_choke = tk.BooleanVar(value=False)
        
        toggles = ttk.Frame(footer, style='Card.TFrame')
        toggles.pack(side=tk.RIGHT, pady=10)
        ttk.Checkbutton(toggles, text="Routes", variable=self.toggle_routes, command=self.update_display).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(toggles, text="Pheromones", variable=self.toggle_phero, command=self.update_display).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(toggles, text="Chokepoints", variable=self.toggle_choke, command=self.update_display).pack(side=tk.LEFT, padx=5)

        right_card = tk.Frame(content, bg=self.colors["bg_card"], bd=1, relief="flat", width=450)
        right_card.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))
        right_card.pack_propagate(False)

        ttk.Label(right_card, text="Population Analytics", style='Title.TLabel').pack(anchor=tk.W, padx=20, pady=(20, 5))

        self.chart_fig = Figure(figsize=(4.5, 6), dpi=100)
        self.chart_fig.patch.set_facecolor(self.colors["bg_card"])
        self.ax_fit = self.chart_fig.add_subplot(211)
        self.ax_gap = self.chart_fig.add_subplot(212)
        
        self.chart_canvas = FigureCanvasTkAgg(self.chart_fig, master=right_card)
        self.chart_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10)

        export_frame = ttk.Frame(right_card, style='Card.TFrame')
        export_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=20, pady=20)
        ttk.Label(export_frame, text="Export Screenshot Path", style='MetricLabel.TLabel').pack(anchor=tk.W, pady=(0, 5))
        
        path_frame = ttk.Frame(export_frame, style='Card.TFrame')
        path_frame.pack(fill=tk.X)
        self.export_path = tk.StringVar(value=str(Path.cwd() / "diagnostic_export.png"))
        tk.Entry(path_frame, textvariable=self.export_path, font=('Segoe UI', 9)).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(path_frame, text="Browse", command=self._browse_path).pack(side=tk.LEFT, padx=5)
        ttk.Button(path_frame, text="Export", command=self._export_screenshot).pack(side=tk.LEFT)

    def _navigate_gen(self, delta):
        current = self.current_gen.get()
        try:
            idx = self.generations.index(current)
            new_idx = max(0, min(len(self.generations) - 1, idx + delta))
            self.current_gen.set(self.generations[new_idx])
            self.update_display()
        except ValueError:
            pass

    def _style_axes(self, ax, title, xlabel, ylabel):
        ax.set_facecolor(self.colors["bg_card"])
        ax.set_title(title, fontdict={'fontsize': 11, 'fontweight': 'bold', 'family': 'sans-serif'}, pad=10)
        ax.set_xlabel(xlabel, fontdict={'fontsize': 9, 'color': self.colors["text_muted"]})
        ax.set_ylabel(ylabel, fontdict={'fontsize': 9, 'color': self.colors["text_muted"]})
        ax.tick_params(colors=self.colors["text_muted"], labelsize=8)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color(self.colors["border"])
        ax.spines['bottom'].set_color(self.colors["border"])
        ax.grid(True, axis='y', linestyle='--', alpha=0.3, color=self.colors["text_muted"])

    def _browse_path(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")])
        if filepath: self.export_path.set(filepath)

    def _export_screenshot(self):
        self.root.update()
        x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        img = ImageGrab.grab(bbox=(x, y, x+w, y+h))
        img.save(self.export_path.get())

    def update_display(self):
        data = self.snapshots[self.current_gen.get()]
        self.best_cost_var.set(f"{data['metadata']['best_cost']:,.4f}")
        self.mean_cost_var.set(f"{data['metadata']['mean_cost']:,.4f}")

        mock_routes = []
        if self.toggle_routes.get():
            for r_data in data['layers']['routes']:
                path = [MockEdge(MockNode(r_data[i]['lat'], r_data[i]['lon']), 
                                 MockNode(r_data[i+1]['lat'], r_data[i+1]['lon'])) 
                        for i in range(len(r_data) - 1)]
                mock_routes.append(MockRoute(path))

        mock_phero = {}
        if self.toggle_phero.get():
            for p in data['layers']['pheromones']:
                edge = p['edge']
                key = (edge[0]['lon'], edge[0]['lat'], edge[1]['lon'], edge[1]['lat'])
                mock_phero[key] = p['intensity']

        chokes = data['layers']['chokepoints'] if self.toggle_choke.get() else None
        hub = data['metadata']['topological_hub']

        all_lats = [pt['lat'] for r_data in data['layers']['routes'] for pt in r_data]
        all_lons = [pt['lon'] for r_data in data['layers']['routes'] for pt in r_data]
        calculated_bounds = (min(all_lats), max(all_lats), min(all_lons), max(all_lons)) if all_lats else (8.145, 8.315, 124.135, 124.305)

        visualizer = StaticVisualizer(bounds=calculated_bounds, routes=mock_routes, pheromones=mock_phero, chokepoints=chokes, topological_hub=hub)
        pil_image = visualizer.draw()
        pil_image.thumbnail((800, 800), Image.Resampling.LANCZOS)
        
        self.tk_img = ImageTk.PhotoImage(pil_image)
        self.map_label.config(image=self.tk_img)

        self.ax_fit.clear()
        self.ax_fit.hist(data['distributions']['fitness'], bins=12, range=self.fit_range, color=self.colors["accent"], edgecolor='white', alpha=0.85)
        self.ax_fit.set_xlim(self.fit_range)
        self.ax_fit.set_ylim(0, self.max_y_fit)
        self._style_axes(self.ax_fit, "Fitness Distribution", "System Cost", "Frequency")

        self.ax_gap.clear()
        self.ax_gap.hist(data['distributions']['unserved_proxy'], bins=12, range=self.gap_range, color='#e83e8c', edgecolor='white', alpha=0.85)
        self.ax_gap.set_xlim(self.gap_range)
        self.ax_gap.set_ylim(0, self.max_y_gap)
        self._style_axes(self.ax_gap, "System Demand-Service Gap Distribution", "Total Demand-Service Gap", "Frequency")

        self.chart_fig.tight_layout(pad=2.0)
        self.chart_canvas.draw()

if __name__ == "__main__":
    root = tk.Tk()
    app = OptimizerDashboard(root)
    root.mainloop()