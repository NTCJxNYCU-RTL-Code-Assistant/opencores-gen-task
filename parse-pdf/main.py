import os
import weave
import comtypes.client
from gpt_parser import parse_pdf


def find_path_with(path, word_list: str):
    # 取得所有父資料夾名稱
    folders = [p.lower() for p in os.path.normpath(path).split(os.sep)]
    return any(word in folders for word in word_list)


def sort_spec_path(spec_path_dict: dict[str, list[str]]):
    # 排序 spec 檔案
    key_order = ["pdf", "doc", "md", "README_FILE", "SPEC_FILE"]
    file_path_list: list[str] = []
    for key in key_order:
        if key in spec_path_dict:
            list_to_sort = spec_path_dict[key]
            list_to_sort.sort(key=lambda x: not "spec" in x.lower())
            file_path_list.extend(list_to_sort)

    file_path_list.sort(key=lambda x: not find_path_with(x, ["doc", "docs"]))
    file_path_list.sort(key=lambda x: not find_path_with(x, ["trunk"]))

    return file_path_list


def convert_doc_to_pdf(doc_path: str, output_path: str):
    wdFormatPDF = 17
    word = comtypes.client.CreateObject("Word.Application")
    doc = word.Documents.Open(os.path.abspath(doc_path))
    doc.SaveAs(os.path.abspath(output_path), FileFormat=wdFormatPDF)
    doc.Close()
    word.Quit()


if __name__ == "__main__":
    import dotenv
    import shutil
    import json

    os.makedirs("parsed", exist_ok=True)
    project_pdfs: list[tuple[str, list[str]]] = []

    project_skipped = os.listdir("parsed")

    with open("spec_paths.json", "r", encoding="utf-8") as f:
        project_spec_filepaths: dict[str, str] = json.load(f)

    dotenv.load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    base_url = os.getenv("OPENROUTER_BASEE_URL")
    model = os.getenv("OPENROUTER_MODEL")
    weave.init("gptpdf")

    for idx, (project_name, spec_path) in enumerate(project_spec_filepaths.items()):
        print(f"Processing {idx + 1}/{len(project_spec_filepaths)}: {project_name}...")
        print(f"Spec path: {spec_path}")

        output_dir = f"parsed/{project_name}"
        os.makedirs(output_dir, exist_ok=True)

        if project_name in project_skipped:
            print(f"Skipping {project_name}...")
            continue

        if spec_path.endswith(".pdf"):
            parse_pdf(
                spec_path,
                output_dir=output_dir,
                api_key=api_key,
                base_url=base_url,
                model=model,
                gpt_worker=6,
            )
        elif spec_path.endswith(".doc") or spec_path.endswith(".docx"):
            pdf_path = f"{output_dir}/{os.path.basename(spec_path).split('.')[0]}.pdf"
            convert_doc_to_pdf(spec_path, pdf_path)
            print("Convert doc to pdf")
            parse_pdf(
                pdf_path,
                output_dir=output_dir,
                api_key=api_key,
                base_url=base_url,
                model=model,
                gpt_worker=6,
            )
        else:
            print("Copy spec")
            shutil.copy(spec_path, f"{output_dir}/{os.path.basename(spec_path)}")
