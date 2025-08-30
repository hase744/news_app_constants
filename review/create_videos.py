# ======== バッチ実行ランナー ===============================================
from pathlib import Path
import json
import os
import sys
import traceback
import io
import cv2
import math
import numpy as np
import pyopenjtalk
from PIL import ImageFont, ImageDraw, Image
from moviepy.editor import AudioFileClip, ImageSequenceClip
from scipy.io import wavfile

NEWS_DIR = Path("generated_news")
IMAGES_DIR = Path("generated_images")
VIDEOS_DIR = Path("generated_videos")

def inputJP(name, img, text, x, y, size, color, output):
    font = ImageFont.truetype('ipam.ttf', int(size))
    img_pil = Image.fromarray(img)
    draw = ImageDraw.Draw(img_pil)
    draw.text((x, y), text, font=font, fill=color)
    output_img = np.array(img_pil)
    if output == 1:
        cv2.imshow(name, output_img)
        cv2.waitKey(1)
    return output_img

def _load_image(image_src):
    # ローカル or URL の両対応（requests不要）
    if isinstance(image_src, str) and image_src.startswith(("http://", "https://")):
        with urllib.request.urlopen(image_src) as resp:
            data = resp.read()
        image_array = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        return img
    else:
        return cv2.imread(image_src, cv2.IMREAD_COLOR)

def generate_assets(title, body_text, image_src, out_basename="output"):
    """
    引数:
      title:        動画/画像のタイトル（画像の上部に載せる）
      body_text:    ナレーション＆字幕に使う本文
      image_src:    画像のURL または ローカルパス
      out_basename: 出力ファイル名のベース（例: 'news1' -> news1.mp4, images/news1_subtitle.jpg）
    戻り値:
      dict: {'video': path, 'subtitle_image': path, 'wav': path}
    """
    # 出力先準備（元コード準拠: images/ を使用）
    images_dir = Path("images")
    images_dir.mkdir(parents=True, exist_ok=True)

    # === 1) 音声生成（本文）==================================================
    text = body_text  # 既存変数名を維持
    x, sr = pyopenjtalk.tts(text)
    wav_path = f"{out_basename}.wav"
    wavfile.write(wav_path, sr, x.astype(np.int16))
    duration = len(x) / sr
    print("WAVファイルの再生時間:", duration, "秒")

    # === 2) 画像読み込み ======================================================
    image = _load_image(image_src)
    if image is None:
        raise FileNotFoundError(f"画像が読み込めませんでした: {image_src}")
    cv2.imwrite(str(images_dir / f'{out_basename}.jpg'), image)
    height, width, _ = image.shape

    # === 3) テキストレイアウト準備（元の数値は極力維持）=======================
    # font = cv2.FONT_HERSHEY_SIMPLEX  # 未使用（Pillowで描画）
    font_scale = 5
    font_thickness = 10
    text_color = (255, 255, 255)  # 白色
    text_size = 30
    text_x = 0
    text_y = height - text_size * 2

    # 本文を横幅に合わせて分割（元ロジック維持）
    frames = []
    text_count = int(width / text_size)
    text_count = max(1, text_count)  # 0除算/空分割の防御のみ追加
    split_text = [text[i:i + text_count] for i in range(0, len(text), text_count)]

    # duration に合わせてフレームレートを決定（元ロジック維持）
    fps = len(split_text) / duration if duration > 0 else 1
    print(f'fps: {fps}')

    # === 4) フレーム生成（本文字幕を各フレームに）=============================
    # MoviePyはRGB想定だが、元の inputJP は BGR->RGB 変換してから渡していたので維持
    base_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    for text_unit in split_text:
        frame = inputJP("Frame", base_rgb, text_unit, text_x, text_y, text_size, text_color, 0)
        frames.append(frame)

    # === 5) 動画生成 ==========================================================
    output_video_path = f"{out_basename}.mp4"
    audio_clip = AudioFileClip(wav_path)
    clip = ImageSequenceClip(frames, fps=fps)
    clip = clip.set_audio(audio_clip)
    clip.write_videofile(
        output_video_path,
        codec="libx264",            # H.264
        audio_codec="aac",          # AAC-LC
        ffmpeg_params=[
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p"
        ]
    )

    # === 6) サブタイトル画像（タイトル文字を上部に描画）========================
    # 元コードでは最後に text_size = width/30, y = text_size で draw
    # ここは title を載せる（関数引数の意図に合わせる）
    title_size = width / 30
    title_x = 0
    title_y = title_size
    # 画像への描画はBGRで保持していた image を使用、inputJPはRGB想定なので変換
    rgb_for_title = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image_with_title = inputJP("Frame", rgb_for_title, title, title_x, title_y, title_size, text_color, 0)
    # 保存時はBGRに戻す
    bgr_title = cv2.cvtColor(image_with_title, cv2.COLOR_RGB2BGR)
    subtitle_path = str(images_dir / f'{out_basename}_subtitle.jpg')
    cv2.imwrite(subtitle_path, bgr_title)

    print("動画が生成されました:", output_video_path)
    os.remove(wav_path)
    return {
        'video': output_video_path,
        'subtitle_image': subtitle_path,
        'wav': wav_path
    }


def find_image_path(json_stem: str, keyword: str) -> Path | None:
    """
    generated_images/<json名>/<keyword>.(png|jpg|jpeg) を探す
    """
    base = IMAGES_DIR / json_stem
    # 拡張子ゆらぎに対応
    for ext in [".png", ".jpg", ".jpeg", ".PNG", ".JPG", ".JPEG"]:
        p = base / f"{keyword}{ext}"
        if p.exists():
            return p
    return None

def load_items_from_json(json_path: Path) -> list[dict]:
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # 想定フォーマット: [{"keyword": "...", "title": "...", "body": "..."}...]
    if not isinstance(data, list):
        raise ValueError(f"{json_path} は配列ではありません")
    normed = []
    for i, item in enumerate(data):
        try:
            keyword = str(item["keyword"])
            title = str(item["title"])
            body = str(item["body"])
        except Exception as e:
            raise ValueError(f"{json_path} の {i} 番目要素が不足: {e}")
        normed.append({"keyword": keyword, "title": title, "body": body})
    return normed

def make_out_basename(json_stem: str, keyword: str) -> Path:
    """
    出力ベースパス（拡張子なし）:
      generated_videos/<json名>/<keyword>
    例:
      generated_videos/baseball/ホームラン
    """
    out_dir = VIDEOS_DIR / json_stem
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / keyword

def main():
    if not NEWS_DIR.exists():
        print(f"[ERROR] ディレクトリが見つかりません: {NEWS_DIR}", file=sys.stderr)
        sys.exit(1)

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    (Path("images")).mkdir(exist_ok=True)  # generate_assets 内の出力用

    json_files = sorted(p for p in NEWS_DIR.glob("*.json"))
    if not json_files:
        print(f"[WARN] JSON がありません: {NEWS_DIR}")
        return

    successes = []
    failures = []

    for json_path in json_files:
        json_stem = json_path.stem  # 例: "baseball"
        print(f"\n=== 処理開始: {json_path} ===")
        try:
            items = load_items_from_json(json_path)
        except Exception as e:
            print(f"[ERROR] JSON 読み込み失敗: {json_path}: {e}", file=sys.stderr)
            failures.append({"json": str(json_path), "error": str(e)})
            continue

        for it in items:
            keyword = it["keyword"]
            title = it["title"]
            body = it["body"]

            # 画像パス探索
            img_path = find_image_path(json_stem, keyword)
            if img_path is None:
                err = f"画像が見つかりません: {IMAGES_DIR}/{json_stem}/{keyword}.(png|jpg|jpeg)"
                print(f"[ERROR] {err}", file=sys.stderr)
                failures.append({
                    "json": str(json_path),
                    "keyword": keyword,
                    "title": title,
                    "error": err
                })
                continue

            # 出力先（拡張子なしのベース）を作成
            out_base = make_out_basename(json_stem, keyword)
            # すでに同名の mp4 がある場合はスキップ（再生成したいならこの分岐を削除）
            mp4_path = out_base.with_suffix(".mp4")
            if mp4_path.exists():
                print(f"[SKIP] 既に存在: {mp4_path}")
                successes.append({
                    "json": str(json_path),
                    "keyword": keyword,
                    "title": title,
                    "video": str(mp4_path),
                    "skipped": True
                })
                continue

            print(f"[RUN] 動画生成: json={json_stem} keyword={keyword}")
            try:
                result = generate_assets(
                    title=title,
                    body_text=body,
                    image_src=str(img_path),
                    out_basename=str(out_base)  # ここが肝：保存先を指定
                )
                print(f"[OK] {result['video']}")
                successes.append({
                    "json": str(json_path),
                    "keyword": keyword,
                    "title": title,
                    "video": result.get("video"),
                    "wav": result.get("wav"),
                    "subtitle_image": result.get("subtitle_image"),
                    "duration_sec": result.get("duration_sec"),
                    "fps": result.get("fps"),
                })
            except Exception as e:
                print(f"[ERROR] 生成失敗: json={json_stem} keyword={keyword}: {e}", file=sys.stderr)
                traceback.print_exc()
                failures.append({
                    "json": str(json_path),
                    "keyword": keyword,
                    "title": title,
                    "error": str(e)
                })

    # 結果サマリを保存
    summary = {
        "successes": successes,
        "failures": failures
    }
    summary_path = VIDEOS_DIR / "batch_summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n=== バッチ完了 ===")
    print(f"成功: {len(successes)} / 失敗: {len(failures)}")
    print(f"サマリ: {summary_path}")

if __name__ == "__main__":
    main()
