import os
import re
import csv
from collections import defaultdict

# ---- Configurable keyword logic (filename-only) ----
INCLUDE_TOKENS = {
    "tb", "testbench", "test", "bench", "sim", 
    "tbtop", "tb_top", "uvm_tb", "tbbench"
}

EXCLUDE_TOKENS = {
    "stub", "stubs", "rtl", "synth", "synthesis", "lib", "util", "docs", "doc",
    "inc", "include", "ip", "wrapper", "pkg", "package", "core", "cfg", "config",
    "dpi", "dpiheader", "data", "golden", "mem", "fifo", "asm", "driver", "model",
    "dut", "timescale"
}

# ---- Language mapping by extension ----
EXT_TO_LANG = {
    ".sv": "SystemVerilog",
    ".svh": "SystemVerilog",
    ".v": "Verilog",
    ".vh": "Verilog",
    ".vhd": "VHDL",
    ".vhdl": "VHDL",
    ".py": "Python",
    ".c": "C",
    ".cc": "C++",
    ".cpp": "C++",
}
ALLOWED_EXTS = set(EXT_TO_LANG.keys())


def tokenize_name(name: str):
    """Split filename into lowercase tokens."""
    return [t for t in re.split(r"[^a-z0-9]+", name.lower()) if t]


def looks_like_tb(filename: str) -> bool:
    """Decide if a file is likely a testbench based on filename only."""
    base = os.path.basename(filename)
    stem, ext = os.path.splitext(base)

    if ext.lower() not in ALLOWED_EXTS:
        return False

    tokens = set(tokenize_name(stem))

    # Exclude easy false positives.
    if tokens & EXCLUDE_TOKENS:
        return False

    # Include if any positive token matched.
    if tokens & INCLUDE_TOKENS:
        return True

    # Special case: exact filename "tb"
    if stem.lower() == "tb":
        return True

    # Heuristic: tb_* or *_tb
    if re.search(r"(?:^tb_|_tb$)", stem.lower()):
        return True

    return False


def infer_language(path: str) -> str:
    """Infer testbench language from file extension."""
    ext = os.path.splitext(path)[1].lower()
    return EXT_TO_LANG.get(ext, "Unknown")


def natural_sort_key(s: str):
    """Windows-like natural sorting."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]


def find_projects(base_dir: str):
    """
    Treat each first-level subdirectory under base_dir as a project root.
    Return:
      total_projects, projects_with_tb_count, projects_map
    where projects_map: { project_name: { 'files': [paths], 'langs': set([...]) } }
    """
    try:
        subdirs = [
            d for d in os.listdir(base_dir)
            if os.path.isdir(os.path.join(base_dir, d))
        ]
    except FileNotFoundError:
        print(f"Base directory not found: {base_dir}")
        return 0, 0, {}

    subdirs.sort(key=natural_sort_key)

    total_projects = len(subdirs)
    proj_map = {d: {"files": [], "langs": set()} for d in subdirs}

    for proj in subdirs:
        proj_root = os.path.join(base_dir, proj)
        for root, _, files in os.walk(proj_root):
            for f in files:
                full = os.path.join(root, f)
                if looks_like_tb(full):
                    proj_map[proj]["files"].append(full)
                    proj_map[proj]["langs"].add(infer_language(full))

    projects_with_tb = sum(1 for p in proj_map.values() if p["files"])
    return total_projects, projects_with_tb, proj_map


# ---------------- CSV Export ----------------

def export_detailed_csv(csv_path, proj_map):
    """Write detailed CSV with one row per testbench file."""
    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Project", "TestbenchFile", "Language"])
        for proj in sorted(proj_map.keys(), key=natural_sort_key):
            for tb in sorted(proj_map[proj]["files"], key=natural_sort_key):
                w.writerow([proj, tb, infer_language(tb)])


def export_summary_csv(csv_path, proj_map):
    """Write summary CSV with one row per project."""
    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Project", "HasTestbench", "Languages", "TB_File_Count"])
        for proj in sorted(proj_map.keys(), key=natural_sort_key):
            info = proj_map[proj]
            has_tb = "Yes" if info["files"] else "No"
            langs = ",".join(sorted(info["langs"])) if info["langs"] else ""
            w.writerow([proj, has_tb, langs, len(info["files"])])


# ---------------- Markdown Export ----------------

def _format_ascii_table(rows):
    """
    Format a list of rows (list of strings) as an ASCII table with monospaced alignment.
    Returns the table string (without code fences). Assumes rows[0] is header.
    """
    # compute widths
    col_count = len(rows[0])
    widths = [0] * col_count
    for r in rows:
        for i in range(col_count):
            widths[i] = max(widths[i], len(str(r[i])))

    # build lines
    def fmt_row(r):
        return " | ".join(str(r[i]).ljust(widths[i]) for i in range(col_count))

    header = fmt_row(rows[0])
    sep = "-+-".join("-" * widths[i] for i in range(col_count))
    body = [fmt_row(r) for r in rows[1:]]

    lines = [header, sep] + body
    return "\n".join(lines)


def export_markdown(md_path, proj_map, total_projects, projects_with_tb):
    """
    Export Markdown report with:
      - overview
      - summary as monospaced ASCII table (inside a code block, aligned)
      - detailed per-project file list
    Paths in details are full absolute paths.
    """
    # Prepare summary rows
    rows = [["Project", "HasTestbench", "Languages", "TB_File_Count"]]
    for proj in sorted(proj_map.keys(), key=natural_sort_key):
        info = proj_map[proj]
        has_tb = "Yes" if info["files"] else "No"
        langs = ", ".join(sorted(info["langs"])) if info["langs"] else ""
        rows.append([proj, has_tb, langs, str(len(info["files"]))])

    ascii_table = _format_ascii_table(rows)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# OpenCores Testbench Report\n\n")
        f.write(f"- **Total Projects:** {total_projects}\n")
        f.write(f"- **Projects with Testbench:** {projects_with_tb}\n\n")

        f.write("## Project Summary (monospaced table)\n\n")
        f.write("```\n")
        f.write(ascii_table)
        f.write("\n```\n")

        f.write("\n## Detailed Testbench Files\n\n")
        for proj in sorted(proj_map.keys(), key=natural_sort_key):
            info = proj_map[proj]
            if not info["files"]:
                continue
            f.write(f"### {proj}\n\n")
            for tb in sorted(info["files"], key=natural_sort_key):
                f.write(f"- `{os.path.abspath(tb)}`\n")
            f.write("\n")


if __name__ == "__main__":
    # Use raw string on Windows to avoid backslash escape issues.
    BASE_DIR = r"E:\Yuren\Researsh\project\opencores_downloads\downloads"  # change as needed
    CSV_SUMMARY = "opencores_tb_summary.csv"
    CSV_DETAILED = "opencores_tb_report.csv"
    MD_REPORT = "opencores_tb_report.md"

    total, with_tb, proj_map = find_projects(BASE_DIR)

    # CSVs
    export_summary_csv(CSV_SUMMARY, proj_map)
    export_detailed_csv(CSV_DETAILED, proj_map)

    # Markdown
    export_markdown(MD_REPORT, proj_map, total, with_tb)

    print(f"Summary CSV:  {CSV_SUMMARY}")
    print(f"Detailed CSV: {CSV_DETAILED}")
    print(f"Markdown:     {MD_REPORT}")
