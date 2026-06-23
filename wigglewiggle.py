#!/usr/bin/env python
import os
import glob
import json
import hashlib
import argparse
from datetime import datetime
import magic
import attrs
import cattrs
import imagehash
from imagehash import ImageHash
from PIL import Image, ImageOps

# Configuration
TMP_LOCATION = "/tmp"

def _hash_unstructure(h: ImageHash) -> str:
    return str(h)

def _hash_structure(s: str, cls) -> ImageHash:
    # Handle the special cases that failed
    if "," in s:
        # crop_resistant_hash stores multiple hashes separated by commas
        return imagehash.hex_to_multihash(s)

    # Try the standard conversion
    try:
        return imagehash.hex_to_hash(s)
    except:
        # Fallback for colorhash or other formats
        return imagehash.hex_to_flathash(s, hashsize=3)

cattrs.global_converter.register_unstructure_hook(ImageHash, _hash_unstructure)
cattrs.global_converter.register_structure_hook(ImageHash, _hash_structure)

def _dt_structure(obj: str, _) -> datetime:
    return datetime.fromisoformat(obj)

cattrs.global_converter.register_unstructure_hook(datetime, datetime.isoformat)
cattrs.global_converter.register_structure_hook(datetime, _dt_structure)

@attrs.define
class HashSet:
    perceptual: ImageHash = None
    average: ImageHash = None
    difference: ImageHash = None
    wavelet: ImageHash = None
    color: ImageHash = None
    crop_resist: ImageHash = None
    crypto: str = None

    @classmethod
    def of_image(cls, img: Image):
        built = cls()
        built.perceptual = imagehash.phash(img)
        built.average = imagehash.average_hash(img)
        built.difference = imagehash.dhash(img)
        built.wavelet = imagehash.whash(img)
        built.color = imagehash.colorhash(img, binbits=3)
        built.crop_resist = imagehash.crop_resistant_hash(img)
        return built

@attrs.define
class HashedImage:
    uid: str
    date: datetime
    path: str = None
    hashes: HashSet = None

    @classmethod
    def from_file(cls, file: str):
        with Image.open(file) as loaded_img:
            exif = loaded_img.getexif()
            date_str = exif.get(36867) if exif else None
            found_ctime = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S') if date_str else datetime.fromtimestamp(os.path.getmtime(file))
            built = cls(uid=hashlib.sha256(file.encode()).hexdigest(), date=found_ctime)
            built.path = file
            built.hashes = HashSet.of_image(loaded_img)
            with open(file, 'rb') as f:
                built.hashes.crypto = hashlib.md5(f.read()).hexdigest()
        return built

    def best_version(self):
        return self.path, self.hashes

hashdb: dict[str, HashedImage] = {}

def backup_db(root: str):
    with open(os.path.join(root, "_hashes.json"), "w") as hf:
        json.dump([cattrs.unstructure(x) for x in hashdb.values()], hf)

def restore_db(root: str):
    global hashdb
    hashdb = {}
    db_path = os.path.join(root, "_hashes.json")
    if os.path.exists(db_path):
        with open(db_path, "r") as hf:
            tmp_data = json.load(hf)
            for itm in tmp_data:
                built = cattrs.structure(itm, HashedImage)
                hashdb[built.uid] = built

def run_hashes_on_directory(directory: str):
    restore_db(directory)
    target_files = [f for f in glob.glob(os.path.join(directory, "**", "*"), recursive=True)
                    if os.path.isfile(f) and "image/" in magic.from_file(f, mime=True)]

    for file in target_files:
        uid = hashlib.sha256(file.encode()).hexdigest()
        if uid not in hashdb:
            try:
                hashdb[uid] = HashedImage.from_file(file)
                print(f"Added: {file}")
            except Exception as e:
                print(f"Error {file}: {e}")
    backup_db(directory)

def find_wigglegrams(thresh: int) -> list[list[HashedImage]]:
    date_sorted = sorted(list(hashdb.values()), key=lambda x: x.date)
    wigglers, this_wiggler = [], []
    for i in range(1, len(date_sorted)):
        dist = date_sorted[i].hashes.perceptual - date_sorted[i - 1].hashes.perceptual
        if 0 < dist < thresh:
            if not this_wiggler: this_wiggler.append(date_sorted[i - 1])
            this_wiggler.append(date_sorted[i])
        elif this_wiggler:
            wigglers.append(this_wiggler)
            this_wiggler = []
    if this_wiggler: wigglers.append(this_wiggler)
    return wigglers

def make_wigglegram(filename: str, imgs: list[HashedImage], frame_duration: int = 150, max_size: int = 1500):
    pillows = []
    for img in imgs:
        # Load and correct orientation
        gottem = Image.open(img.path)
        gottem = ImageOps.exif_transpose(gottem)

        # Increase max_size for better resolution
        gottem.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        pillows.append(gottem)

    full_sequence = pillows + pillows[::-1][1:-1]

	# Quantize to a high-quality palette
    # full_sequence = [p.convert('P', palette=Image.Palette.ADAPTIVE, colors=256) for p in full_sequence]

    # Save with higher quality settings
    full_sequence[0].save(
        filename,
        save_all=True,
        append_images=full_sequence[1:],
        duration=frame_duration,
        loop=0,
        optimize=False,          # Disabling optimization can sometimes help quality
        method=6,                # 6 is the highest compression/quality effort for GIF
        subrectangles=True       # Stores only the changes between frames, reducing size
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", "-d", required=True)
    parser.add_argument("action", choices=["hash", "export"])
    parser.add_argument("--threshold", "-t", help="How similar an image must be to be considered a wigglegram.", type=int, default=10)
    parser.add_argument("--max-size", "-s", type=int, default=800, help="Max width/height of the GIF.")
    args = parser.parse_args()

    if args.action == "hash":
        run_hashes_on_directory(args.directory)
    elif args.action == "export":
        restore_db(args.directory)
        all_found = find_wigglegrams(args.threshold)
        for i, wig in enumerate(all_found):
            fname = os.path.join(args.directory, f"wiggle_{i}.gif")
            make_wigglegram(fname, wig, max_size=args.max_size)
            print(f"Exported: {fname}")

