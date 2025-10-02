import os


def load_project_names():
    projects_names: list[str] = []
    with open("gen-stimuli/opencores_tb_report.md", "r", encoding="utf-8") as f:
        lines = f.readlines()

        # 找到表格開始和結束的位置
        table_start = -1
        table_end = -1

        for i, line in enumerate(lines):
            if line.strip() == "```" and i > 0 and "Project Summary" in lines[i - 2]:
                table_start = i + 1  # 跳過表格標題行
                break

        for i in range(table_start, len(lines)):
            if lines[i].strip() == "```":
                table_end = i
                break

        if table_start == -1 or table_end == -1:
            return projects_names

        # 解析表格內容
        for i in range(table_start + 1, table_end):  # 跳過標題行和分隔線
            line = lines[i].strip()
            if not line or line.startswith("-"):  # 跳過空行和分隔線
                continue

            # 分割表格列
            columns = [col.strip() for col in line.split("|")]
            if len(columns) >= 3:  # 確保有足夠的列
                project_name = columns[0].strip()
                has_testbench = columns[1].strip()

                if has_testbench == "Yes":
                    projects_names.append(project_name)

    return projects_names


def find_pdf_path(project_name: str):
    # 遞迴遍歷 dir_path 下的所有檔案
    dir_path = f"../opencores_downloads/{project_name}/{project_name}"
    file_path_list: list[str] = []
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            if file.endswith(".pdf"):
                file_path_list.append(os.path.join(root, file))

    def is_in_doc_folder(path, word_list: str):
        # 取得所有父資料夾名稱
        folders = [p.lower() for p in os.path.normpath(path).split(os.sep)]
        return any(word in folders for word in word_list)

    file_path_list.sort(key=lambda x: not is_in_doc_folder(x, ["doc", "docs"]))
    file_path_list.sort(key=lambda x: not is_in_doc_folder(x, ["trunk"]))

    return file_path_list


if __name__ == "__main__":
    import dotenv
    import shutil
    import weave
    import json
    from gpt_parser import parse_pdf

    os.makedirs("parsed", exist_ok=True)
    project_names = load_project_names()
    project_pdfs: list[tuple[str, list[str]]] = []
    project_without_pdfs: list[str] = []
    project_skipped = os.listdir("parsed")
    project_names = [
        project_name
        for project_name in project_names
        if project_name not in project_skipped
    ]

    # for idx, project_name in enumerate(project_names):
    #     pdf_path_list = find_pdf_path(project_name)
    #     if len(pdf_path_list) > 0:
    #         project_pdfs.append((project_name, pdf_path_list))
    #     else:
    #         project_without_pdfs.append(project_name)

    # with open("project_pdfs.json", "w", encoding="utf-8") as f:
    #     json.dump(project_pdfs, f)
    # with open("project_without_pdfs.json", "w", encoding="utf-8") as f:
    #     json.dump(project_without_pdfs, f)

    with open("project_pdfs.json", "r", encoding="utf-8") as f:
        project_pdfs = json.load(f)
    with open("project_without_pdfs.json", "r", encoding="utf-8") as f:
        project_without_pdfs = json.load(f)

    print(f"Total projects to process: {len(project_names)}")
    print(f"Total projects with pdfs: {len(project_pdfs)}")
    print(f"Total projects without pdfs: {len(project_without_pdfs)}")

    dotenv.load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    base_url = os.getenv("OPENROUTER_BASEE_URL")
    model = os.getenv("OPENROUTER_MODEL")
    weave.init("gptpdf")

    for idx, (project_name, pdf_path_list) in enumerate(project_pdfs):
        pdf_path = pdf_path_list[0]
        print(f"Processing {idx + 1}/{len(project_pdfs)}: {pdf_path}...")
        output_dir = f"parsed/{project_name}"
        shutil.rmtree(output_dir, ignore_errors=True)
        parse_pdf(
            pdf_path,
            output_dir=output_dir,
            api_key=api_key,
            base_url=base_url,
            model=model,
            gpt_worker=6,
        )
