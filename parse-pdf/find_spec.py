import os
import json


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


def generate_spec_filepaths():
    all_project_names = os.listdir("../opencores_downloads")
    tb_project_names = set(load_tb_project_names())

    project_spec_filepaths: dict[str, dict[str, list[str] | bool]] = {}

    for project_name in all_project_names:
        project_spec: dict[str, list[str] | bool] = {}
        if project_name not in tb_project_names:
            project_spec = {"No Testbench": True}

        dir_path = f"../opencores_downloads/{project_name}/{project_name}"
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                if file.lower().endswith(".v") or file.lower().endswith(".sv"):
                    continue
                elif (
                    file.lower().endswith(".c")
                    or file.lower().endswith(".cpp")
                    or file.lower().endswith(".h")
                ):
                    continue
                elif file.endswith(".py"):
                    continue
                elif file.endswith(".pdf"):
                    if "pdf" not in project_spec:
                        project_spec["pdf"] = []
                    project_spec["pdf"].append(os.path.join(root, file))
                elif file.endswith(".md"):
                    if "md" not in project_spec:
                        project_spec["md"] = []
                    project_spec["md"].append(os.path.join(root, file))
                elif file.endswith(".doc") or file.endswith(".docx"):
                    if "doc" not in project_spec:
                        project_spec["doc"] = []
                    project_spec["doc"].append(os.path.join(root, file))
                elif "spec" in file.lower():
                    if "SPEC_FILE" not in project_spec:
                        project_spec["SPEC_FILE"] = []
                    project_spec["SPEC_FILE"].append(os.path.join(root, file))
                elif "readme" in file.lower():
                    if "README_FILE" not in project_spec:
                        project_spec["README_FILE"] = []
                    project_spec["README_FILE"].append(os.path.join(root, file))
        if len(project_spec) > 0:
            project_spec_filepaths[project_name] = project_spec

    with open("project_spec_filepaths.json", "w", encoding="utf-8") as f:
        json.dump(project_spec_filepaths, f)

    print(f"Total projects: {len(all_project_names)}")
    print(
        f"Total projects with spec & tb: {len([project_name for project_name in project_spec_filepaths if 'No Testbench' not in project_spec_filepaths[project_name]])}"
    )

    return project_spec_filepaths


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
            list_to_sort.sort(key=lambda x: not "readme" in x.lower())
            list_to_sort.sort(key=lambda x: not "spec" in x.lower())
            list_to_sort.sort(key=lambda x: not find_path_with(x, ["doc", "docs"]))
            list_to_sort.sort(key=lambda x: not find_path_with(x, ["trunk"]))
            file_path_list.extend(list_to_sort)

    return file_path_list


if __name__ == "__main__":
    project_spec_filepaths = generate_spec_filepaths()
    # with open("project_spec_filepaths.json", "r", encoding="utf-8") as f:
    #     project_spec_filepaths = json.load(f)
    spec_paths: dict[str, str] = {}
    for project_name, spec_path_dict in project_spec_filepaths.items():
        if "No Testbench" in spec_path_dict:
            continue
        spec_path_list = sort_spec_path(spec_path_dict)
        spec_paths[project_name] = spec_path_list[0]
    with open("spec_paths.json", "w", encoding="utf-8") as f:
        json.dump(spec_paths, f)
