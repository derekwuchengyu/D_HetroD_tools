import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import cv2
import os
import sys

class FastTrajectoryAnnotator:
    def __init__(self, root, traj_file="trajectory.csv", bg_file="00_background.png"):
        self.root = root
        self.root.title("Fast Trajectory Annotator")

        # Load data
        if not os.path.exists(traj_file):
            raise FileNotFoundError(f"Cannot find {traj_file}")
        self.df = pd.read_csv(traj_file)
        self.df.sort_values(by=["frame","trackId"], inplace=True)
        self.frames = sorted(self.df["frame"].unique())
        self.current_idx = 0
        self.max_idx = len(self.frames)-1
        self.playing = False

        # Load background
        if not os.path.exists(bg_file):
            raise FileNotFoundError(f"Cannot find {bg_file}")
        self.bg = cv2.cvtColor(cv2.imread(bg_file), cv2.COLOR_BGR2RGB)
        self.bg_h, self.bg_w = self.bg.shape[:2]
        self.ortho_px_to_meter = 0.0499967249445942  # Example, adjust based on your map scaling

        # Annotations
        self.annotations = []

        # Matplotlib figure
        self.fig, self.ax = plt.subplots(figsize=(8,8))
        self.ax.imshow(self.bg, extent=[-self.bg_w/2,self.bg_w/2,-self.bg_h/2,self.bg_h/2])
        self.ax.set_aspect("equal")
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().grid(row=0,column=0,rowspan=20)

        # UI panel
        self.setup_ui()

        # Frame label
        self.frame_label = tk.Label(root,text=f"Frame: {self.frames[self.current_idx]}")
        self.frame_label.grid(row=12,column=0)

        # Patch storage
        self.bbox_patches = {}  # trackId -> Rectangle
        self.bbox_texts = {}    # trackId -> Text

        # Initialize patches for first frame
        self.init_frame_patches()

        # Keyboard bindings
        root.bind("<Right>", lambda e:self.next_frame())
        root.bind("<Left>", lambda e:self.prev_frame())
        root.bind("<space>", lambda e:self.toggle_play())

        # Play loop
        self.root.after(100, self.play_loop)

    def setup_ui(self):
        tk.Label(self.root,text="Scenario Description").grid(row=0,column=1,sticky="w")
        self.scenario_entry = tk.Entry(self.root,width=30)
        self.scenario_entry.grid(row=1,column=1)

        tk.Label(self.root,text="Category").grid(row=2,column=1,sticky="w")
        self.category_entry = ttk.Combobox(self.root, values=["cut-in","lane-change","stop","turn"])
        self.category_entry.grid(row=3,column=1)

        tk.Label(self.root,text="Referred Object").grid(row=4,column=1,sticky="w")
        self.referred_combo = ttk.Combobox(self.root, values=[])
        self.referred_combo.grid(row=5,column=1)

        tk.Label(self.root,text="Related Objects").grid(row=6,column=1,sticky="w")
        self.related_listbox = tk.Listbox(self.root, selectmode="multiple", height=6)
        self.related_listbox.grid(row=7,column=1)

        self.reset_btn = tk.Button(self.root,text="Reset",command=self.reset_annotations)
        self.reset_btn.grid(row=8,column=1)

        tk.Button(self.root,text="<< Prev",command=self.prev_frame).grid(row=9,column=1,sticky="w")
        tk.Button(self.root,text="Play/Pause",command=self.toggle_play).grid(row=10,column=1,sticky="w")
        tk.Button(self.root,text="Next >>",command=self.next_frame).grid(row=11,column=1,sticky="w")

    def init_frame_patches(self):
        df_f = self.df[self.df["frame"]==self.frames[self.current_idx]]
        for _,row in df_f.iterrows():
            tid = row["trackId"]
            rect = Rectangle((0,0),1,1,edgecolor="red",facecolor="none",lw=2)
            txt = self.ax.text(0,0,str(tid),color="red",fontsize=8,ha="center")
            self.ax.add_patch(rect)
            self.bbox_patches[tid] = rect
            self.bbox_texts[tid] = txt
        self.update_frame_fast()

    def update_frame_fast(self):
        self.frame_label.config(text=f"Frame: {self.frames[self.current_idx]}")
        df_f = self.df[self.df["frame"]==self.frames[self.current_idx]]
        track_ids = list(df_f["trackId"].unique())
        self.referred_combo["values"] = track_ids
        self.related_listbox.delete(0,tk.END)
        for tid in track_ids:
            self.related_listbox.insert(tk.END, tid)

        colors = plt.cm.tab10.colors
        for i, (_,row) in enumerate(df_f.iterrows()):
            tid = row["trackId"]
            rect = self.bbox_patches.get(tid)
            txt = self.bbox_texts.get(tid)
            if rect and txt:
                x = row["xCenter"]/self.ortho_px_to_meter
                y = -row["yCenter"]/self.ortho_px_to_meter
                l = row["length"]/self.ortho_px_to_meter
                w = row["width"]/self.ortho_px_to_meter
                heading = -row["heading"]
                heading = heading if heading>=0 else heading+360
                rect.set_width(l)
                rect.set_height(w)
                rect.set_xy((x-l/2,y-w/2))
                rect.angle = heading
                txt.set_position((x,y))
        self.canvas.draw()
        self.save_annotation()

    def save_annotation(self):
        frame_id = self.frames[self.current_idx]
        scenario = self.scenario_entry.get()
        category = self.category_entry.get()
        referred = self.referred_combo.get()
        related = [self.related_listbox.get(i) for i in self.related_listbox.curselection()]
        ann = {"frame":frame_id,
               "scenario description":scenario,
               "category":category,
               "referred":referred,
               "related":",".join(map(str,related))}
        self.annotations.append(ann)
        pd.DataFrame(self.annotations).drop_duplicates(subset=["frame"]).to_csv("annotations.csv",index=False)

    def next_frame(self):
        if self.current_idx < self.max_idx:
            self.current_idx += 1
            self.update_frame_fast()

    def prev_frame(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self.update_frame_fast()

    def toggle_play(self):
        self.playing = not self.playing

    def play_loop(self):
        if self.playing and self.current_idx<self.max_idx:
            self.next_frame()
        self.root.after(100,self.play_loop)

    def reset_annotations(self):
        self.annotations = []
        pd.DataFrame(self.annotations).to_csv("annotations.csv",index=False)
        messagebox.showinfo("Reset","Annotations reset.")

if __name__=="__main__":
    traj_file = "trajectory.csv"
    bg_file = "00_background.png"
    if len(sys.argv)>1: traj_file = sys.argv[1]
    if len(sys.argv)>2: bg_file = sys.argv[2]
    root = tk.Tk()
    app = FastTrajectoryAnnotator(root,traj_file,bg_file)
    root.mainloop()