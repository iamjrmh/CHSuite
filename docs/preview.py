import tkinter as tk
from PIL import Image, ImageTk
import requests
from io import BytesIO
from bs4 import BeautifulSoup
import os

class DiscordPreviewer:
    def __init__(self, root, file_path):
        self.root = root
        self.root.title("Discord Embed Simulator")
        self.root.geometry("550x650")
        self.root.configure(bg="#313338")

        # 1. Parse Data from local index.html
        data = self.get_meta_data(file_path)

        # UI Container
        main_frame = tk.Frame(self.root, bg="#313338", padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)

        # Title
        tk.Label(main_frame, text=data['title'], fg="#00A8FC", bg="#313338", 
                 font=("Helvetica", 12, "bold"), wraplength=480, justify="left").pack(anchor="w")

        # Description
        tk.Label(main_frame, text=data['desc'], fg="#DBDEE1", bg="#313338", 
                 font=("Helvetica", 10), wraplength=480, justify="left").pack(anchor="w", pady=(5, 10))

        # Image Embed Area
        self.img_label = tk.Label(main_frame, bg="#2B2D31")
        self.img_label.pack(fill="x", pady=5)

        self.display_image(data['img'])

    def get_meta_data(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
        
        # Helper to find by property or name
        find_meta = lambda k: (soup.find("meta", property=k) or soup.find("meta", attrs={"name": k}))
        
        return {
            'title': find_meta("og:title")["content"] if find_meta("og:title") else "Untitled",
            'desc': find_meta("og:description")["content"] if find_meta("og:description") else "No description.",
            'img': find_meta("og:image")["content"] if find_meta("og:image") else None
        }

    def display_image(self, img_source):
        try:
            # TRY LOCAL FIRST (if the file exists in your Images folder)
            # This allows you to see the GUI before you even push to GitHub
            local_name = img_source.split('/')[-1].split('?')[0].replace('%20', ' ')
            local_path = os.path.join("Images", local_name)

            if os.path.exists(local_path):
                img_data = Image.open(local_path)
                print(f"Loading local image: {local_path}")
            else:
                # TRY DOWNLOAD
                print(f"Attempting to download: {img_source}")
                headers = {'User-Agent': 'Mozilla/5.0'}
                r = requests.get(img_source, headers=headers, timeout=5)
                r.raise_for_status()
                img_data = Image.open(BytesIO(r.content))

            # Resize for GUI
            w, h = img_data.size
            new_w = 480
            new_h = int(new_w * (h / w))
            img_data = img_data.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            self.photo = ImageTk.PhotoImage(img_data)
            self.img_label.config(image=self.photo)
        except Exception as e:
            self.img_label.config(text=f"IMAGE LOAD FAILED\n\nError: {e}\n\nURL: {img_source}", 
                                  fg="#F23F42", font=("Consolas", 9), pady=20)

if __name__ == "__main__":
    root = tk.Tk()
    if os.path.exists("index.html"):
        app = DiscordPreviewer(root, "index.html")
        root.mainloop()
    else:
        print("Error: index.html not found in this directory.")