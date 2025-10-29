import openai
import weave
import os
import base64
import re
from dotenv import load_dotenv

REMOVE_USELESS_PNG_PROMPT = """
You are a professional digital circuit verification engineer.

[Task]
I will give you 3 example images of USELESS images, and then give you an image to judge.
You need to tell me if this image is useful or not.

[Rules]
1. Only output "useful" or "useless", DO NOT output anything else.
2. Do not explain or output irrelevant text, directly output the content from the image. For example, it is strictly forbidden to output examples like "Here is the result I generated based on the image content:", instead you should directly output "useful" or "useless".
"""


def encode_image_to_base64(image_path: str) -> str:
    """將圖片轉換為 base64 編碼"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


EXAMPLE_1_BASE64 = encode_image_to_base64("example_1.png")
EXAMPLE_2_BASE64 = encode_image_to_base64("example_2.png")
EXAMPLE_3_BASE64 = encode_image_to_base64("example_3.png")


@weave.op()
def remove_useless_png(image_path: str) -> bool:
    # 讀取待判斷的圖片
    target_image_base64 = encode_image_to_base64(image_path)

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": REMOVE_USELESS_PNG_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Example 1 (USELESS): This image is only a Opencores project logo, so it is useless.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{EXAMPLE_1_BASE64}"
                        },
                    },
                    {
                        "type": "text",
                        "text": "Example 2 (USELESS): This image is a header or a footer of a PDF file, so it is useless.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{EXAMPLE_2_BASE64}"
                        },
                    },
                    {
                        "type": "text",
                        "text": "Example 3 (USELESS): This image is part of outline of a PDF file, so it is useless.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{EXAMPLE_3_BASE64}"
                        },
                    },
                    {
                        "type": "text",
                        "text": "Now, please judge if the following image is useful or useless:",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{target_image_base64}"
                        },
                    },
                ],
            },
        ],
    )
    return response.choices[0].message.content.strip() == "useless"


if __name__ == "__main__":
    load_dotenv()
    openai.api_key = os.getenv("OPENAI_API_KEY")

    if not openai.api_key:
        print("錯誤：請設定 OPENAI_API_KEY 環境變數")
        exit(1)

    weave.init("remove-useless-png")

    target_dir = "parsed"

    for project_dir in os.listdir(target_dir):
        project_dir = os.path.join(target_dir, project_dir)
        md_path = f"{project_dir}/output.md"
        if not os.path.exists(md_path):
            continue

        print(f"Processing {project_dir}...")
        with open(md_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        for image in os.listdir(project_dir):
            if not image.endswith(".png"):
                continue
            if remove_useless_png(os.path.join(project_dir, image)):
                print(f"Remove useless image: {image}")
                os.remove(os.path.join(project_dir, image))
                md_content = re.sub(
                    rf"!\[[^\]]*\]\({re.escape(image)}\)", "", md_content
                )
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
