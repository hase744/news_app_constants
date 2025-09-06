import pyopenjtalk
import numpy as np
import cv2
from scipy.io import wavfile
from moviepy.editor import *
from PIL import ImageFont, ImageDraw, Image
from pathlib import Path
import urllib.request
import os

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
    text_size = 20
    text_x = 0
    text_y = height - text_size * 2

    # 本文を横幅に合わせて分割（元ロジック維持）
    frames = []
    text_count = int(width / text_size)
    text_count = max(1, text_count)  # 0除算/空分割の防御のみ追加
    print(f'text_count: {text_count}')
    split_text = [text[i:i + text_count] for i in range(0, len(text), text_count)]
    print(f'split_text: {split_text}')

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

# --- 使い方例 ---
assets = generate_assets(
    title="加藤太郎氏 外務大臣就任",
    body_text="""内閣改造において、政府は異例の人事を発表し、元宇宙飛行士である加藤太郎氏を新たな外務大臣に任命することを発表しました。この人事は、日本の外交政策に新たな視点を取り入れるためのものであり、国内外から大きな注目を集めています。加藤氏は、かつて国際宇宙ステーションでの長期滞在経験を持つ宇宙飛行士として知られており、その間に培われた国際協力や外交能力が高く評価されました。内閣府の報道官は、加藤氏の任命について、「彼の宇宙での経験は、地球外の環境での協力と対話の重要性を理解する上で貴重なものであり、日本の外交政策に新たな展望をもたらすでしょう」とコメントしました。加藤氏自身も、「宇宙から見た地球は、国境や人種の壁を超えた一体性が感じられるものです。私はこの経験を活かし、日本の外交政策の発展に尽力したいと思います」と述べています。加藤氏の外務大臣就任により、日本の外交政策がよりダイナミックで先進的な方向へ進むことが期待されています。""",
    image_src="input_image.jpg",  # or "https://example.com/xxx.jpg"
    out_basename="output"
)
print(assets)
