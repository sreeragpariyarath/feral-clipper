"""Open-source models that run on your own GPU (free, no API calls).

  Clip         - OpenCLIP ViT-B-32 (LAION). Scores frames against text ("a police chase", "a menu screen")
                 and turns each frame into a fingerprint so it can tell what is NEW (novelty memory).
  AudioTagger  - PANNs Cnn14 (AudioSet, 527 sound classes). Hears sirens, gunfire, explosions,
                 helicopters, screaming, crashes... even when chat and the streamer are quiet.

Weights are downloaded once by:  python tools/setup_models.py
"""
import json
import subprocess
from pathlib import Path

from clipper.common import ROOT

import numpy as np

MODELS = ROOT / "models"
PANNS_CKPT = MODELS / "Cnn14_mAP=0.431.pth"
CLIP_ARCH, CLIP_TAG = "ViT-B-32", "laion2b_s34b_b79k"
MEMORY = MODELS / "clip_memory.npy"


def device():
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


# ------------------------------------------------------------------ CLIP prompts
ACTION = [
    "a police chase in a video game", "police cars with sirens chasing a car", "a police helicopter in the sky",
    "a helicopter flying low over a city", "a car crash in a video game", "a car flipping through the air",
    "a huge explosion with fire", "a burning car", "a shootout with guns", "a character shooting a gun",
    "a fist fight in a video game", "a wild animal attacking", "an alligator", "a crocodile in a swamp",
    "a shark in the ocean", "a dolphin jumping out of the water", "a bear in the woods", "a big monster creature",
    "a speedboat racing on water", "a jet ski on the ocean", "an airboat in a swamp", "an airplane flying",
    "a plane crash", "a skydiver with a parachute", "a motorcycle stunt jump", "a sports car racing at high speed",
    "a character falling from a great height", "a crowd of people running in panic", "a tornado or storm",
    "a strange creature never seen before",
]
BORING = [
    "a video game pause menu", "a video game map screen", "a loading screen", "a black screen",
    "an inventory or shop menu", "a phone screen inside a video game", "a settings menu with text",
    "a character standing still in a room", "a character walking slowly down a street",
    "a person talking to a webcam", "a character sitting in a parked car", "a dialogue scene with two people talking",
    "a cinematic cutscene with black bars",
]
UNSAFE = [
    "a shirtless man in underwear", "a woman in underwear", "a strip club with dancers", "nudity",
    "a sexual scene", "blood and gore",
]


def knowledge_prompts():
    try:
        k = json.loads((ROOT / "gta6_knowledge.json").read_text(encoding="utf-8"))
        return [f"a video game screenshot of {x['look']}" for x in k.get("discoveries", []) if x.get("look")]
    except Exception:
        return []


class Clip:
    def __init__(self, pretrained=CLIP_TAG):
        import open_clip
        import torch
        self.torch = torch
        self.dev = device()
        self.model, _, self.prep = open_clip.create_model_and_transforms(
            CLIP_ARCH, pretrained=pretrained, cache_dir=str(MODELS / "clip"))
        self.model = self.model.to(self.dev).eval()
        if self.dev == "cuda":
            self.model = self.model.half()
        tok = open_clip.get_tokenizer(CLIP_ARCH)
        self.know = knowledge_prompts()
        self.prompts = ACTION + self.know + BORING + UNSAFE
        self.n_act = len(ACTION) + len(self.know)
        self.n_bor = len(BORING)
        with torch.no_grad():
            t = self.model.encode_text(tok(self.prompts).to(self.dev))
            self.text = t / t.norm(dim=-1, keepdim=True)

    def embed(self, paths, batch=64):
        from PIL import Image
        out = []
        with self.torch.no_grad():
            for i in range(0, len(paths), batch):
                ims = self.torch.stack([self.prep(Image.open(p).convert("RGB")) for p in paths[i:i + batch]])
                ims = ims.to(self.dev)
                if self.dev == "cuda":
                    ims = ims.half()
                e = self.model.encode_image(ims)
                out.append((e / e.norm(dim=-1, keepdim=True)).float().cpu().numpy())
        return np.concatenate(out) if out else np.zeros((0, 512), np.float32)

    def score(self, emb):
        """Per frame: action / boring / unsafe probability and the best matching prompt."""
        text = self.text.float().cpu().numpy()
        logits = 100.0 * emb @ text.T
        logits -= logits.max(axis=1, keepdims=True)
        p = np.exp(logits)
        p /= p.sum(axis=1, keepdims=True)
        a, b = self.n_act, self.n_act + self.n_bor
        res = []
        for row in p:
            best = int(row.argmax())
            res.append({"action": float(row[:a].sum()), "boring": float(row[a:b].sum()),
                        "unsafe": float(row[b:].sum()), "best": self.prompts[best],
                        "best_kind": "action" if best < a else "boring" if best < b else "unsafe"})
        return res


def novelty(emb, times, min_dt=120.0, memory=None):
    """1 - similarity to the most similar frame seen elsewhere (>min_dt away, or in past VODs).
    High = this looks unlike anything else -> possibly something new."""
    sim = emb @ emb.T
    t = np.asarray(times, dtype=np.float64)
    far = np.abs(t[:, None] - t[None, :]) >= min_dt
    sim = np.where(far, sim, -1.0)
    best = sim.max(axis=1)
    if memory is not None and len(memory):
        best = np.maximum(best, (emb @ memory.T).max(axis=1))
    best = np.where(best < -0.5, 1.0, best)            # nothing far enough away -> not novel
    return (1.0 - best).astype(float)


def load_memory():
    try:
        return np.load(MEMORY)
    except Exception:
        return np.zeros((0, 512), np.float32)


def save_memory(emb, cap=20000):
    """Remember a sample of this VOD's frames so the same places/things are not 'new' next time."""
    mem = load_memory()
    keep = emb[:: max(1, len(emb) // 400)]
    mem = np.concatenate([mem, keep.astype(np.float32)])[-cap:]
    MEMORY.parent.mkdir(parents=True, exist_ok=True)
    np.save(MEMORY, mem)


# ------------------------------------------------------------------ PANNs audio
SOUNDS = {   # AudioSet label -> weight (how much it means "something is happening")
    "Siren": 1.0, "Police car (siren)": 1.0, "Emergency vehicle": 0.9, "Civil defense siren": 0.6,
    "Gunshot, gunfire": 1.0, "Machine gun": 1.0, "Fusillade": 1.0, "Artillery fire": 0.8, "Cap gun": 0.6,
    "Explosion": 1.0, "Boom": 0.8, "Burst, pop": 0.4, "Fire": 0.5,
    "Helicopter": 0.9, "Aircraft": 0.6, "Fixed-wing aircraft, airplane": 0.6, "Jet engine": 0.6,
    "Skidding": 0.8, "Tire squeal": 0.8, "Car alarm": 0.6, "Vehicle horn, car horn, honking": 0.4,
    "Smash, crash": 0.9, "Breaking": 0.6, "Glass": 0.4, "Shatter": 0.7,
    "Screaming": 0.9, "Yell": 0.6, "Shout": 0.5, "Laughter": 0.5, "Belly laugh": 0.7,
    "Motorboat, speedboat": 0.6, "Roar": 0.6, "Growling": 0.6, "Dog": 0.3, "Bark": 0.3,
}


class AudioTagger:
    SR = 32000

    def __init__(self, checkpoint=PANNS_CKPT, load_weights=True):
        import torch
        from panns_inference.models import Cnn14
        from panns_inference.config import labels
        self.torch = torch
        self.dev = device()
        self.labels = labels
        self.model = Cnn14(sample_rate=self.SR, window_size=1024, hop_size=320, mel_bins=64,
                           fmin=50, fmax=14000, classes_num=len(labels))
        if load_weights:
            ck = torch.load(str(checkpoint), map_location="cpu", weights_only=False)
            self.model.load_state_dict(ck["model"])
        self.model = self.model.to(self.dev).eval()
        self.idx = {lab: (labels.index(lab), w) for lab, w in SOUNDS.items() if lab in labels}

    def tag_file(self, media, t_from=0.0, t_to=None, chunk=5.0, batch=32, progress=None):
        """Stream audio through ffmpeg (no big temp file). Returns [{t, score, top:{label:prob}}] per chunk,
        t = chunk middle in seconds (absolute)."""
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{t_from:.2f}", "-i", str(media)]
        if t_to:
            cmd += ["-t", f"{t_to - t_from:.2f}"]
        cmd += ["-vn", "-ac", "1", "-ar", str(self.SR), "-f", "s16le", "-"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        n = int(self.SR * chunk)
        out, buf, starts, k = [], [], [], 0
        try:
            while True:
                raw = proc.stdout.read(n * 2)
                if not raw:
                    break
                a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                if len(a) < n // 2:
                    break
                if len(a) < n:
                    a = np.pad(a, (0, n - len(a)))
                buf.append(a)
                starts.append(t_from + k * chunk)
                k += 1
                if len(buf) == batch:
                    out += self._run(buf, starts, chunk)
                    buf, starts = [], []
                    if progress:
                        progress(k * chunk)
            if buf:
                out += self._run(buf, starts, chunk)
        finally:
            proc.stdout.close()
            proc.wait()
        return out

    def _run(self, buf, starts, chunk):
        x = self.torch.from_numpy(np.stack(buf)).to(self.dev)
        with self.torch.no_grad():
            p = self.model(x, None)["clipwise_output"].float().cpu().numpy()
        res = []
        for s, row in zip(starts, p):
            hits = {lab: float(row[i]) for lab, (i, w) in self.idx.items() if row[i] >= 0.08}
            score = max([row[i] * w for lab, (i, w) in self.idx.items()] or [0.0])
            top = dict(sorted(hits.items(), key=lambda kv: -kv[1])[:4])
            res.append({"t": round(s + chunk / 2, 2), "score": round(float(score), 3), "top": top})
        return res


def audio_at(tags, t, radius=10.0):
    """Strongest sound event within +-radius seconds of t."""
    best = {"score": 0.0, "top": {}}
    for x in tags:
        if abs(x["t"] - t) <= radius and x["score"] > best["score"]:
            best = x
    return best
