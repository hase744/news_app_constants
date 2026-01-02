import json
from collections import defaultdict
from collections import Counter

with open('data/categories.json', 'r', encoding='utf-8') as f:
    categories_data = json.load(f)
valid_category_names = list(categories_data.keys())

with open('data/channels.json', 'r', encoding='utf-8') as f:
    channels_data = json.load(f)

with open('data/enumerations.json', 'r', encoding='utf-8') as f:
    enumerations = json.load(f)

with open('data/category_enumerations.json', 'r', encoding='utf-8') as f:
    category_enumerations = json.load(f)

with open('data/authors.json', 'r', encoding='utf-8') as f:
    authors_data = json.load(f)
author_names = {
    a["japanese_name"]
    for a in authors_data
    if "japanese_name" in a and a.get("channel_exist") is not False
}

invalid_urls = []
unique_invalid_categories = []
print(valid_category_names)

for entry in channels_data:
    url = entry['url']
    categories = entry['categories'].split()
    
    invalid_categories = [cat for cat in categories if cat not in valid_category_names]
    
    if invalid_categories:
        #print(f"{url} に無効なカテゴリ: {invalid_categories}")
        invalid_urls.append(url)
        # Add invalid categories to unique_invalid_categories if not already present
        for cat in invalid_categories:
            if cat not in unique_invalid_categories:
                unique_invalid_categories.append(cat)
print(unique_invalid_categories)

if not invalid_urls:
    print("すべてのチャンネルに有効なカテゴリのみが含まれています。")

invalid_groups = {}

urls = [entry['url'] for entry in channels_data]
url_counts = Counter(urls)
duplicate_urls = [url for url, count in url_counts.items() if count > 1]

if duplicate_urls:
    print("重複しているURLがあります:")
    for url in duplicate_urls:
        print(url)
else:
    print("channels.json に重複URLはありません。")

for group_name, keys in category_enumerations.items():
    missing_keys = [key for key in keys if key not in enumerations]
    if missing_keys:
        invalid_groups[group_name] = missing_keys

if invalid_groups:
    print("以下のグループに存在しないキーが含まれています:")
    for group, missing in invalid_groups.items():
        print(f"{group} に存在しないキー: {missing}")
else:
    print("すべてのグループのキーはenumerations.jsonに存在しています。")


channel_authors = []
for entry in channels_data:
    author = entry.get("author")
    if author:  # None や "" を除外
        channel_authors.append(author)

channel_authors_set = set(channel_authors)

# ① channels.json の author にあるのに authors.json に name がないもの
invalid_channel_authors = {}  # {author名: [url1, url2, ...]}
for entry in channels_data:
    author = entry.get("author")
    if author and author not in author_names:
        invalid_channel_authors.setdefault(author, []).append(entry["url"])

if invalid_channel_authors:
    print("channels.json の author に存在するが authors.json の name に存在しないもの:")
    for author, urls in invalid_channel_authors.items():
        print(f"  author: {author}")
        for url in urls:
            print(f"    - {url}")
else:
    print("channels.json の author はすべて authors.json の name に存在します。")

# ② authors.json の name にあるのに channels.json の author に一度も出てこないもの
unused_authors = [name for name in author_names if name not in channel_authors_set]

if unused_authors:
    print("authors.json の name にあるが channels.json の author に使われていないもの:")
    for name in unused_authors:
        print(f"  - {name}")
else:
    print("authors.json の name はすべて channels.json の author から参照されています。")

authors_by_name = defaultdict(list)

for idx, a in enumerate(authors_data):
    name = a.get("name")
    if not name:
        continue
    authors_by_name[name].append((idx, a))

duplicate_names = {name: rows for name, rows in authors_by_name.items() if len(rows) > 1}

if duplicate_names:
    print("authors.json に name の重複があります:\n")

    for name, rows in duplicate_names.items():
        print(f"■ name: {name}（{len(rows)}件）")

        # 比較対象のキー（必要に応じて増やせる）
        compare_keys = ["japanese_name", "is_group", "image_url", "alias_names"]

        # 値を集める
        values_by_key = {
            key: {json.dumps(row[1].get(key), ensure_ascii=False) for row in rows}
            for key in compare_keys
        }

        for idx, row in rows:
            print(f"  - 行 {idx}:")
            for key in compare_keys:
                print(f"      {key}: {row.get(key)}")

        # 差分チェック
        diff_keys = [key for key, vals in values_by_key.items() if len(vals) > 1]

        if diff_keys:
            print("  ⚠️ 内容が一致していないキー:")
            for key in diff_keys:
                print(f"      - {key}")
        else:
            print("  ✓ 内容はすべて一致")

        print()

else:
    print("authors.json に name の重複はありません。")

# ----------------------------
# official_website / image_url の「Noneでない値」の重複チェックを追加
# ----------------------------

def normalize_url(value: str) -> str:
    """
    None/空は呼び出し元で除外する想定。
    ここでは「末尾スラッシュ」「前後空白」を吸収する。
    必要なら lower() も入れるが、URLはパスが大小区別され得るので慎重に。
    """
    v = value.strip()
    # 末尾スラッシュを統一（"https://x.com/abc" と "https://x.com/abc/" を同一扱い）
    if v.endswith("/"):
        v = v[:-1]
    return v

def collect_duplicates(authors_data, field: str):
    """
    authors_data の field(official_website/image_url) の値が
    Noneでなく、正規化後に重複しているものを集める。
    """
    values_map = defaultdict(list)  # {normalized_value: [(idx, author_obj), ...]}
    for idx, a in enumerate(authors_data):
        raw = a.get(field)
        if raw is None:
            continue
        if isinstance(raw, str):
            if raw.strip() == "":
                continue
            val = normalize_url(raw)
        else:
            # 文字列以外（想定外）が来たら除外するか、文字列化するかは好み
            continue

        values_map[val].append((idx, a))

    duplicates = {val: rows for val, rows in values_map.items() if len(rows) > 1}
    return duplicates

for field in ["official_website", "image_url"]:
    duplicates = collect_duplicates(authors_data, field)

    if duplicates:
        print(f"\nauthors.json に {field} の重複があります:\n")
        for val, rows in duplicates.items():
            print(f"■ {field}: {val}（{len(rows)}件）")
            for idx, a in rows:
                # 見やすいように name / japanese_name も表示
                print(f"  - 行 {idx}: name={a.get('name')} japanese_name={a.get('japanese_name')}")
    else:
        print(f"\nauthors.json に {field} の重複はありません。")
