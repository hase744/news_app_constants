import json
from collections import Counter

with open('data/categories.json', 'r', encoding='utf-8') as f:
    categories_data = json.load(f)
valid_category_names = list(categories_data.keys())

with open('data/channels.json', 'r', encoding='utf-8') as f:
    channels_data = json.load(f)

with open('data/enumulations.json', 'r', encoding='utf-8') as f:
    enumulations = json.load(f)

with open('data/enumulations_groups.json', 'r', encoding='utf-8') as f:
    enumulation_groups = json.load(f)

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

for group_name, keys in enumulation_groups.items():
    missing_keys = [key for key in keys if key not in enumulations]
    if missing_keys:
        invalid_groups[group_name] = missing_keys

if invalid_groups:
    print("以下のグループに存在しないキーが含まれています:")
    for group, missing in invalid_groups.items():
        print(f"{group} に存在しないキー: {missing}")
else:
    print("すべてのグループのキーはenumulations.jsonに存在しています。")
