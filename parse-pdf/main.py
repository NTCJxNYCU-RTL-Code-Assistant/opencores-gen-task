import os


def load_tb_project_names():
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


def find_path_with(path, word_list: str):
    # 取得所有父資料夾名稱
    folders = [p.lower() for p in os.path.normpath(path).split(os.sep)]
    return any(word in folders for word in word_list)


def find_pdf_path(project_name: str):
    # 遞迴遍歷 dir_path 下的所有檔案
    dir_path = f"../opencores_downloads/{project_name}/{project_name}"
    file_path_list: list[str] = []
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            if file.endswith(".pdf"):
                file_path_list.append(os.path.join(root, file))
    file_path_list.sort(key=lambda x: not find_path_with(x, ["doc", "docs"]))
    file_path_list.sort(key=lambda x: not find_path_with(x, ["trunk"]))

    return file_path_list


# all_project_names = os.listdir("../opencores_downloads")
# project_names = load_tb_project_names()

# project_spec_types: dict[str, set[str]] = {}
# for project_name in project_names:
#     dir_path = f"../opencores_downloads/{project_name}/{project_name}"
#     project_spec_type: set[str] = set()
#     for root, dirs, files in os.walk(dir_path):
#         for file in files:
#             if file.endswith(".pdf"):
#                 project_spec_type.add("pdf")
#             elif file.endswith(".md"):
#                 project_spec_type.add("md")
#             elif file.endswith(".doc") or file.endswith(".docx"):
#                 project_spec_type.add("doc")
#             elif "spec" in file.lower():
#                 project_spec_type.add("SPEC_FILE")
#             elif "readme" in file.lower():
#                 project_spec_type.add("README_FILE")
#     if len(project_spec_type) > 0:
#         project_spec_types[project_name] = project_spec_type

# print(f"Total projects: {len(all_project_names)}")
# print(f"Testbench projects: {len(project_names)}")
# print(f"Testbench projects with spec: {len(project_spec_types)}")
# print(
#     f"Testbench projects with pdf spec: {len([project_name for project_name, spec_type in project_spec_types.items() if 'pdf' in spec_type])}"
# )
# print(
#     f"Testbench projects with md spec: {len([project_name for project_name, spec_type in project_spec_types.items() if 'md' in spec_type])}"
# )
# print(
#     f"Testbench projects with doc spec: {len([project_name for project_name, spec_type in project_spec_types.items() if 'doc' in spec_type])}"
# )
# print(
#     f"Testbench projects with any spec_file spec: {len([project_name for project_name, spec_type in project_spec_types.items() if 'SPEC_FILE' in spec_type])}"
# )
# print(
#     f"Testbench projects with any readme_file spec: {len([project_name for project_name, spec_type in project_spec_types.items() if 'README_FILE' in spec_type])}"
# )

# exit()


if __name__ == "__main__":
    import dotenv
    import shutil
    import weave
    import json
    from gpt_parser import parse_pdf

    os.makedirs("parsed", exist_ok=True)
    project_names = load_tb_project_names()
    project_pdfs: list[tuple[str, list[str]]] = []
    # for idx, project_name in enumerate(project_names):
    #     pdf_path_list = find_pdf_path(project_name)
    #     if len(pdf_path_list) > 0:
    #         project_pdfs.append((project_name, pdf_path_list))

    # with open("project_pdfs.json", "w", encoding="utf-8") as f:
    #     json.dump(project_pdfs, f)

    project_skipped = os.listdir("parsed")
    project_names = [
        project_name
        for project_name in project_names
        if project_name not in project_skipped
    ]

    with open("project_pdfs.json", "r", encoding="utf-8") as f:
        project_pdfs = json.load(f)
        project_pdfs = [
            (project_name, pdf_path_list)
            for project_name, pdf_path_list in project_pdfs
            if project_name in project_names
        ]

    print(f"Total projects to process: {len(project_pdfs)}")

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
