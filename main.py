import openai
import json
from typing import Optional
from openai.types.chat import ChatCompletion

# 輸入 PDF 檔案路徑與文字內容，回傳 GPT-4o 的 JSON 結果


def extract_text_from_pdf(pdf_path: str) -> str:
    # TODO: 實作 PDF 文字提取
    return ""


def call_gpt_4o_api(prompt: str,
                    api_key: str,
                    model: str = "gpt-4o") -> Optional[ChatCompletion]:
    try:
        openai.api_key = api_key
        response = openai.chat.completions.create(model=model,
                                                  messages=[{
                                                      "role": "user",
                                                      "content": prompt
                                                  }])
        return response
    except Exception as e:
        print(f"API 呼叫失敗: {e}")
        return None


def main(pdf_path: str, text: str, api_key: str):
    # 1. 讀取 PDF 內容
    pdf_text = extract_text_from_pdf(pdf_path)
    # 2. 合併 PDF 文字與額外文字
    full_prompt = pdf_text + "\n" + text
    # 3. 呼叫 GPT-4o API
    result = call_gpt_4o_api(full_prompt, api_key)
    # 4. 輸出 JSON 結果
    if result is not None:
        print(result.model_dump_json(indent=4))
    else:
        print("API 回傳為 None")


if __name__ == "__main__":
    # 範例用法，請自行填入 pdf_path、text、api_key
    pdf_path = "your_file.pdf"
    text = "這裡輸入額外的文字內容"
    api_key = "sk-..."
    main(pdf_path, text, api_key)
