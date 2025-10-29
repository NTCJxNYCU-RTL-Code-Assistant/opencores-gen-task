from parse_tb_md import find_projects
import json
from typing import TypedDict, Literal
import os


class Project(TypedDict):
    project_name: str
    enable: Literal[0, 1]
    project_dir: str
    spec_file: str
    testbench_list: list[str]


def find_spec_file(dir_path: str) -> str:
    """
    尋找資料夾中的規格檔案

    規則：
    - 如果只有一個檔案，直接回傳該檔案的 path
    - 如果有多個檔案，優先順序：
      1. .md 檔案
      2. .txt 檔案
      3. 檔名為 README 的檔案（無論大小寫、無論副檔名）
    """
    files = [
        f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))
    ]

    # 如果只有一個檔案，直接回傳
    if len(files) == 1:
        return os.path.join(dir_path, files[0])

    # 如果有多個檔案，按優先順序尋找
    # 1. 優先 .md 檔案
    for file in files:
        if file.endswith(".md"):
            return os.path.join(dir_path, file)

    # 2. 其次 .txt 檔案
    for file in files:
        if file.endswith(".txt"):
            return os.path.join(dir_path, file)

    # 3. 最後是檔名為 README 的檔案（無論大小寫）
    for file in files:
        filename_without_ext = os.path.splitext(file)[0]
        if filename_without_ext.lower() == "readme":
            return os.path.join(dir_path, file)

    return ""


if __name__ == "__main__":
    PROJECT_SOURCE_DIR = "D:/projects/opencores_downloads"
    PARSED_SPEC_DIR = "D:/projects/opencores-gen-task/parsed"
    total, with_tb, proj_map = find_projects(PROJECT_SOURCE_DIR)
    project_list: list[Project] = []
    for project_name, project_info in proj_map.items():
        spec_source_dir = os.path.join(PARSED_SPEC_DIR, project_name)
        if not os.path.exists(spec_source_dir):
            print(f"No spec source dir found for {project_name}")
            continue
        spec_file = find_spec_file(spec_source_dir)
        if not spec_file:
            print(f"No spec file found for {project_name}")
            continue
        project_list.append(
            Project(
                project_name=project_name,
                enable=1,
                project_dir=f"{PROJECT_SOURCE_DIR}/{project_name}",
                spec_file=spec_file,
                testbench_list=project_info["files"],
            )
        )
    with open("projects.json", "w", encoding="utf-8") as f:
        json.dump(project_list, f, ensure_ascii=False, indent=4)
    print(f"Total projects: {len(project_list)}")
