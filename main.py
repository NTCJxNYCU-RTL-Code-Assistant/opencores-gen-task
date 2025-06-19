import openai
import json
from typing import Optional
from openai.types.chat import ChatCompletion
import os


def extract_text_from_pdf(pdf_path: str) -> str:
    # TODO: 實作 PDF 文字提取
    return ""


def call_gpt_4o_api(prompt: str) -> Optional[ChatCompletion]:
    assert model is not None, "OPENAI_MODEL 未設定"
    try:
        response = openai.chat.completions.create(model=model,
                                                  messages=[{
                                                      "role": "user",
                                                      "content": prompt
                                                  }])
        return response
    except Exception as e:
        print(f"API 呼叫失敗: {e}")
        return None


def main(pdf_path: str, text: str):
    pdf_text = extract_text_from_pdf(pdf_path)
    full_prompt = pdf_text + "\n" + text
    result = call_gpt_4o_api(full_prompt)
    if result is not None:
        print(result.model_dump_json(indent=4))
    else:
        print("API 回傳為 None")


if __name__ == "__main__":
    openai.api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    pdf_path = "your_file.pdf"
    text = "這裡輸入額外的文字內容"
    main(pdf_path, text)
