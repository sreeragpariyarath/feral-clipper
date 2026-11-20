"""Download the open-source model weights once (about 1 GB total). Safe to re-run; it resumes.

  python tools/setup_models.py

  - AudioSet labels      (GitHub)        ~30 KB
  - PANNs Cnn14 weights  (Zenodo)        ~330 MB
  - OpenCLIP ViT-B-32    (Hugging Face)  ~600 MB
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # so `clipper` is found when run from tools\

import shutil
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
LABELS = Path.home() / "panns_data" / "class_labels_indices.csv"
LABEL_URLS = [
    "https://raw.githubusercontent.com/qiuqiangkong/audioset_tagging_cnn/master/metadata/class_labels_indices.csv",
    "http://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/class_labels_indices.csv",
]
CKPT_URL = "https://zenodo.org/records/3987831/files/Cnn14_mAP%3D0.431.pth?download=1"


def fetch(urls, dest, min_bytes=1, tries=8):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size >= min_bytes:
        print(f"  ok   {dest.name} already downloaded")
        return True
    part = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, tries + 1):
        for url in urls:
            try:
                have = part.stat().st_size if part.exists() else 0
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                           **({"Range": f"bytes={have}-"} if have else {})})
                with urllib.request.urlopen(req, timeout=60) as r:
                    total = have + int(r.headers.get("Content-Length") or 0)
                    mode = "ab" if (have and r.status == 206) else "wb"
                    if mode == "wb":
                        have = 0
                    with open(part, mode) as f:
                        while True:
                            b = r.read(1 << 20)
                            if not b:
                                break
                            f.write(b)
                            have += len(b)
                            if total > 1 << 20:
                                print(f"\r  ...  {dest.name}: {have / 1e6:.0f}/{total / 1e6:.0f} MB", end="", flush=True)
                if part.stat().st_size >= min_bytes:
                    shutil.move(str(part), str(dest))
                    print(f"\r  ok   {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)            ")
                    return True
            except Exception as e:
                print(f"\n  retry {attempt}/{tries}: {type(e).__name__}: {e}")
                time.sleep(5)
    print(f"  FAILED {dest.name}. Run this script again later (it resumes), or try with a VPN/WARP on.")
    return False


def main():
    print("1/3 AudioSet labels")
    ok = fetch(LABEL_URLS, LABELS, min_bytes=10_000)
    print("2/3 PANNs Cnn14 audio model")
    ok &= fetch([CKPT_URL], MODELS / "Cnn14_mAP=0.431.pth", min_bytes=300_000_000)
    print("3/3 OpenCLIP ViT-B-32 (from Hugging Face)")
    try:
        import os
        os.environ.pop("HF_HUB_OFFLINE", None)
        sys.path.insert(0, str(ROOT))
        from clipper.ai.local_models import Clip
        c = Clip()
        print(f"  ok   CLIP loaded on {c.dev}")
    except Exception as e:
        ok = False
        print(f"  FAILED CLIP: {e}\n  Run again (Hugging Face drops on some networks; VPN/WARP helps).")
    if ok:
        print("\nTesting the audio model...")
        try:
            from clipper.ai.local_models import AudioTagger
            a = AudioTagger()
            print(f"  ok   PANNs loaded on {a.dev}, watching {len(a.idx)} sound types")
        except Exception as e:
            ok = False
            print(f"  FAILED PANNs: {e}")
    print("\nAll models ready." if ok else "\nSome downloads failed; re-run this script.")


if __name__ == "__main__":
    main()
