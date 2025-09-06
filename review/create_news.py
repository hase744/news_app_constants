# generate_fake_news_by_keywords.py
import os
import json
import time
import re
import random
from pathlib import Path
from typing import Dict, Any, List

from dotenv import load_dotenv
load_dotenv()  # .env をロード

# ====== 設定 ======
CATEGORIES_PATH = Path("../data/categories.json")
OUTPUT_DIR = Path("generated_news")
MODEL_NAME = "gemini-1.5-flash"           # 品質を上げたいなら "gemini-1.5-pro"
NUM_KEYWORDS = 10                         # キーワード数
NUM_PER_KEYWORD = 1                       # キーワードあたりニュース件数（要件通り1）
SLEEP_BETWEEN_CALLS_SEC = (0.6, 1.2)      # API 呼び出し間隔
MAX_RETRY = 3                             

# ====== Gemini 初期化 ======
try:
    import google.generativeai as genai
except ImportError:
    raise SystemExit("google-generativeai 未インストール。`pip install google-generativeai` を実行してください。")

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise SystemExit("環境変数 GEMINI_API_KEY が設定されていません。.env を用意し load_dotenv() を呼んでください。")

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(MODEL_NAME)

# ====== ユーティリティ ======
JSON_ARRAY_RE = re.compile(r"\[(?:.|\s)*\]")

def safe_filename(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z._-]+", "_", name).strip("_") or "output"

def extract_first_json_array(text: str) -> List[Any]:
    """
    text から最初の JSON 配列を抽出して list に。
    ```json ... ``` や前後の説明が混ざっていても大まかに対応。
    """
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    m = JSON_ARRAY_RE.search(t)
    if not m:
        raise ValueError("JSON 配列を抽出できませんでした。")
    arr_str = m.group(0).strip().rstrip(",")
    data = json.loads(arr_str)
    if not isinstance(data, list):
        raise ValueError("抽出した JSON が配列ではありません。")
    return data

def normalize_keyword(s: str) -> str:
    s = str(s).strip()
    # 末尾・先頭の記号/番号などを軽く除去
    s = re.sub(r"^[\-\d\.\)\s、,・：:【】\[\]]+", "", s)
    s = re.sub(r"[\s、,・：:【】\[\]]+$", "", s)
    return s

def generate_keywords(category_japanese_name: str, n: int) -> List[str]:
    """
    カテゴリに関連する日本語キーワードを n 個生成。
    JSON 配列（文字列のみ）で返すよう Gemini に指示。
    """
    prompt = f"""あなたは優秀な見出しキュレーターです。カテゴリ「{category_japanese_name}」に強く関連する
日本語の「単語」または「短いフレーズ」をちょうど {n} 個生成してください。

厳守:
- 出力は JSON 配列（文字列のみ）※例: ["〇〇", "△△", ...]
- 各要素は 2〜8 文字程度の日本語を推奨（専門用語なら長くても可）
- 同義・重複・ほぼ同じ表現は避ける
- 政治/宗教/個人攻撃などセンシティブな表現は避け、一般的な概念語にする
- 前後の説明やコードフェンスは不要。JSON 配列のみ。

例（ビジネス）:
["人材育成","業務効率化","資金調達","新規事業","企業買収","ガバナンス","市場調査","価格戦略","物流網","データ活用"]
"""
    resp = model.generate_content(prompt)
    items = extract_first_json_array(resp.text or "")

    # 文字列のみ残し、整形 & 重複排除
    clean = []
    seen = set()
    for it in items:
        if not isinstance(it, str):
            continue
        k = normalize_keyword(it)
        if not k or k in seen:
            continue
        seen.add(k)
        clean.append(k)

    # 数が足りないときは適当に補完（最後の要素にインデックス付与）
    while len(clean) < n and clean:
        clean.append(f"{clean[-1]}{len(clean)+1}")
    return clean[:n]

def prompt_news_for_keyword(category_japanese_name: str, keyword: str) -> str:
    return f"""あなたは編集者です。カテゴリ「{category_japanese_name}」のうち、キーワード「{keyword}」にフォーカスした
完全に架空の最新ニュースを1件、以下の JSON オブジェクトだけで返してください。

制約:
- 出力は JSON オブジェクト1つのみ（コードフェンスや前置き不要）
- 実在の個人への誹謗中傷や機微情報は避ける
- フィクションと分かる語感（〜の見通し、〜の可能性など）を保つ
- タイトル: 18〜48文字程度、日本語
- 本文: 140〜260文字程度、日本語。キーワード「{keyword}」の文脈を自然に含める

フォーマット:
{{
  "title": "（タイトル）",
  "body": "（本文）"
}}
"""

def generate_news_for_keyword(category_japanese_name: str, keyword: str) -> Dict[str, str]:
    prompt = prompt_news_for_keyword(category_japanese_name, keyword)
    for attempt in range(1, MAX_RETRY + 1):
        try:
            resp = model.generate_content(prompt)
            text = (resp.text or "").strip()
            # JSON オブジェクト抽出
            # 単純化: 最初の { ... } を拾う
            m = re.search(r"\{(?:.|\s)*\}", text)
            if not m:
                raise ValueError("JSON オブジェクトが見つかりません。")
            obj = json.loads(m.group(0))
            title = str(obj.get("title", "")).strip()
            body  = str(obj.get("body", "")).strip()
            if len(title) < 8 or len(body) < 80:
                raise ValueError("title/body の長さが不足")
            return {"keyword": keyword, "title": title, "body": body}
        except Exception as e:
            if attempt >= MAX_RETRY:
                # 最後は簡易フォールバックで返す
                return {
                    "keyword": keyword,
                    "title": f"{keyword}：動きが活発化（架空）",
                    "body": f"{category_japanese_name}分野で「{keyword}」に関する取り組みが各地で進んでいる。専門家は今後の展開に注目しており、関係者の間では新たな連携の可能性も語られている。詳細は続報を待ちたい。"
                }
        time.sleep(random.uniform(*SLEEP_BETWEEN_CALLS_SEC))

def main():
    if not CATEGORIES_PATH.exists():
        raise SystemExit(f"{CATEGORIES_PATH} が見つかりません。")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with CATEGORIES_PATH.open("r", encoding="utf-8") as f:
        categories = json.load(f)

    for key, meta in categories.items():
        jp = (meta or {}).get("japanese_name")
        if not jp:
            print(f"[WARN] {key}: japanese_name がないためスキップ")
            continue

        print(f"[INFO] キーワード生成: '{key}'（{jp}） -> {NUM_KEYWORDS}件")
        keywords = generate_keywords(jp, NUM_KEYWORDS)
        # 念のため重複排除 & 上限
        uniq = []
        seen = set()
        for k in keywords:
            if k not in seen:
                uniq.append(k)
                seen.add(k)
        keywords = uniq[:NUM_KEYWORDS]

        results: List[Dict[str, str]] = []
        titles_seen = set()

        print(f"[INFO] ニュース生成（キーワードごと）: total={len(keywords)}")
        for i, kw in enumerate(keywords, 1):
            item = generate_news_for_keyword(jp, kw)
            # タイトル重複回避
            if item["title"] in titles_seen:
                item["title"] = f"{item['title']}（続報）"
            titles_seen.add(item["title"])

            results.append(item)
            print(f"  - {i}/{len(keywords)} [{kw}] {item['title'][:36]}...")
            time.sleep(random.uniform(*SLEEP_BETWEEN_CALLS_SEC))

        out_path = OUTPUT_DIR / f"{safe_filename(key)}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"[DONE] {out_path} に {len(results)} 件を書き出し")

if __name__ == "__main__":
    main()
