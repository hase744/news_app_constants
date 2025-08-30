#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path
from moviepy.editor import VideoFileClip  # pip install moviepy
from tqdm import tqdm  # pip install tqdm

ROOT = Path(__file__).resolve().parent
NEWS_DIR = ROOT / "generated_news"
VIDEO_DIR = ROOT / "generated_videos"
IMAGE_DIR = ROOT / "generated_images"
OUTPUT_PATH = ROOT / "summary.json"

def get_video_duration(video_path: Path):
    if not video_path.exists():
        return None
    try:
        with VideoFileClip(str(video_path)) as clip:
            return int(clip.duration)
    except Exception as e:
        print(f"⚠️ 動画の長さ取得失敗: {video_path} ({e})")
        return None

def build_summary():
    summary = []

    # 全ニュースの総件数をカウント（進捗バーのmaxに必要）
    total_items = 0
    for news_json in NEWS_DIR.glob("*.json"):
        try:
            items = json.loads(news_json.read_text(encoding="utf-8"))
            if isinstance(items, list):
                total_items += len(items)
        except:
            pass

    # tqdm で進捗バー表示
    with tqdm(total=total_items, desc="処理中", ncols=100) as pbar:
        for news_json in sorted(NEWS_DIR.glob("*.json")):
            category = news_json.stem
            items = json.loads(news_json.read_text(encoding="utf-8"))
            if not isinstance(items, list):
                continue

            for item in items:
                keyword = str(item.get("keyword", "")).strip()
                title   = str(item.get("title", "")).strip()
                body    = str(item.get("body", "")).strip()

                video_path = VIDEO_DIR / category / f"{keyword}.mp4"
                image_path = IMAGE_DIR / category / f"{keyword}.png"

                video_str = str(video_path.relative_to(ROOT)) if video_path.exists() else None
                image_str = str(image_path.relative_to(ROOT)) if image_path.exists() else None
                total_seconds = get_video_duration(video_path) if video_path.exists() else None

                summary.append({
                    "category": category,
                    "keyword": keyword,
                    "title": title,
                    "body": body,
                    "video_path": video_str,
                    "image_path": image_str,
                    "total_seconds": total_seconds,
                })

                # append 後に進捗を1つ進める
                pbar.update(1)

    OUTPUT_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"✅ Done: {OUTPUT_PATH} に {len(summary)} 件を書き出しました。")

if __name__ == "__main__":
    build_summary()
