# list_keywords_with_stem.py
from pathlib import Path
import json
import sys
import os
from google import genai
from PIL import Image, UnidentifiedImageError
from io import BytesIO
from dotenv import load_dotenv

GENERATED_DIR = Path("generated_news")
FAILED_PATH = Path("failed_words.json")

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=API_KEY)

def generate_image(key):
    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash-image-preview",
            contents=[f"『{key}』という光景の画像を生成して。必ず文章ではなく画像のみを生成。"],
        )
        cands = getattr(resp, "candidates", None) or []
        parts = (cands[0].content.parts if cands and getattr(cands[0], "content", None) else [])
        for p in parts:
            data = getattr(p, "inline_data", None)
            if data and getattr(data, "data", None):
                try:
                    return Image.open(BytesIO(data.data))
                except UnidentifiedImageError:
                    return None
    except Exception:
        return None
    return None

def failed_add(stem, kw):
    try:
        failed = {}
        if FAILED_PATH.exists():
            failed = json.loads(FAILED_PATH.read_text(encoding="utf-8"))
        failed.setdefault(stem, []).append(kw)
        FAILED_PATH.write_text(json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def main():
    if FAILED_PATH.exists():
        FAILED_PATH.unlink()
    if not GENERATED_DIR.exists():
        print(f"ディレクトリが見つかりません: {GENERATED_DIR}", file=sys.stderr)
        sys.exit(1)

    files = sorted(p for p in GENERATED_DIR.glob("*.json") if p.is_file())
    if not files:
        print("JSON ファイルが見つかりません。", file=sys.stderr)
        sys.exit(1)

    total = 0
    for f in files:
        stem = f.stem
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"# {stem}\t読み込み失敗\t{e}")
            continue

        if not isinstance(data, list):
            print(f"# {stem}\t配列ではありません")
            continue

        outdir = Path("generated_images") / stem
        outdir.mkdir(parents=True, exist_ok=True)

        for i, item in enumerate(data, 1):
            kw = item.get("keyword") if isinstance(item, dict) else None
            title = item.get("title") if isinstance(item, dict) else None
            if not kw:
                continue

            path = outdir / f"{kw}.png"
            print(f"{stem}\t{i:02d}\t{kw}\n{path}")

            # すでに存在していればスキップ
            if path.exists():
                continue

            img = generate_image(title)
            if img:
                try:
                    img.save(path)
                    total += 1
                except Exception:
                    failed_add(stem, kw)
            else:
                failed_add(stem, kw)

    print(f"# total\t{total}")

if __name__ == "__main__":
    main()
