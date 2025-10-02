from docling.document_converter import DocumentConverter
from docling_core.types.doc.base import ImageRefMode

if __name__ == "__main__":
    source = "D:/projects/opencores-gen-task/opencores/bubble_sort_module/doc/BubblesortSpecs.pdf"
    converter = DocumentConverter()
    result = converter.convert(source)
    md_file = result.document.export_to_markdown(
        image_mode=ImageRefMode.REFERENCED)

    with open("./output_docling/bubble_sort.md", "w", encoding="utf-8") as f:
        f.write(md_file)
