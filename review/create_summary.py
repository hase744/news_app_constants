#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path

# ルート（このスクリプトを置いた場所を基準にしたい場合はそのまま）
ROOT = Path(__file__).resolve().parent

NEWS_DIR = ROOT / "generated_news"
VIDEO_DIR = ROOT / "generated_videos"
IMAGE_DIR = ROOT / "generated_images"
OUTPUT_PATH = ROOT / "summary.json"

def build_summary():
    if not NEWS_DIR.exists():
        raise FileNotFoundError(f"ニュースディレクトリが見つかりません: {NEWS_DIR}")

    summary = []  # すべてのカテゴリを一つにまとめる

    # generated_news 配下の *.json を走査
    for news_json in sorted(NEWS_DIR.glob("*.json")):
        category = news_json.stem  # 例: baseball.json -> "baseball"

        # ニュース JSON を読み込み（配列形式を想定）
        try:
            items = json.loads(news_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON パースに失敗しました: {news_json} ({e})")

        if not isinstance(items, list):
            raise ValueError(f"配列形式の JSON を想定しています: {news_json}")

        for i, item in enumerate(items, start=1):
            # 必須キーの取得（無ければ空文字に）
            keyword = str(item.get("keyword", "")).strip()
            title   = str(item.get("title", "")).strip()
            body    = str(item.get("body", "")).strip()

            # ファイル名は keyword と一致する前提（拡張子固定）
            # 例: generated_videos/baseball/ピッチャー.mp4
            #     generated_images/baseball/ピッチャー.png
            video_path = (VIDEO_DIR / category / f"{keyword}.mp4")
            image_path = (IMAGE_DIR / category / f"{keyword}.png")

            # 実在チェック。無ければ None を入れる
            video_str = str(video_path.relative_to(ROOT)) if video_path.exists() else None
            image_str = str(image_path.relative_to(ROOT)) if image_path.exists() else None

            summary.append({
                "category": category,
                "keyword": keyword,
                "title": title,
                "body": body,
                "video_path": video_str,
                "image_path": image_str,
            })

    # まとめて書き出し（UTF-8・日本語可・インデント付き）
    OUTPUT_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"✅ Done: {OUTPUT_PATH} に {len(summary)} 件を書き出しました。")

if __name__ == "__main__":
    build_summary()
