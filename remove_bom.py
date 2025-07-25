# remove_bom.py
from pathlib import Path

path = Path("input/urls1.txt")

with path.open("rb") as f:
    data = f.read()

# Strip UTF-8 BOM if present
if data.startswith(b"\xef\xbb\xbf"):
    print("Stripping BOM from file urls1.txt...")
    data = data[3:]
    with path.open("wb") as f:
        f.write(data)
    print("✅ Done.")
else:
    print("No BOM found. File is clean.")
