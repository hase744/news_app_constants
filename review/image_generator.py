import os
from google import genai
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY") 
client = genai.Client(api_key=API_KEY)

def generate_image(prompt):
    response = client.models.generate_content(
        model="gemini-2.5-flash-image-preview",
        contents=[prompt],
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            print(part.from_text)
            return Image.open(BytesIO(part.inline_data.data))
    return None

# 使用例
img = generate_image("『驚異の守備力！新鋭・星野選手がチームを牽引する可能性』という光景の画像を生成して。必ず文章ではなく画像のみを生成。")
if img:
    img.save("VR・AR.png")
# っぽい画像を生成して。必ず文章ではなく画像のみを生成。
# からイメージできる画像を生成して
# をテーマにした画像を生成して。必ず文章ではなく画像のみを生成。