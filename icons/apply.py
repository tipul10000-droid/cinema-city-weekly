"""Copies one icon option into the site's app icons: python icons/apply.py 1-ticket"""
import sys
from PIL import Image
src = Image.open(f"icons/{sys.argv[1]}.png").convert("RGB")
for n, f in ((180, "apple-touch-icon.png"), (192, "icon-192.png"), (512, "icon-512.png")):
    src.resize((n, n), Image.LANCZOS).save(f"docs/{f}")
