import os
import re
import base64
from typing import List, Tuple, Optional, Any
import fitz
import shapely.geometry as sg
from shapely.validation import explain_validity
from concurrent.futures import as_completed
import logging
from openai import OpenAI
import weave

DEFAULT_PROMPT = """Use markdown syntax to convert the text recognized in the image to markdown format output. You must:
1. Output and use the same language as recognized in the image, for example, if English fields are recognized, the output content must be in English.
2. Do not explain or output irrelevant text, directly output the content from the image. For example, it is strictly forbidden to output examples like "Here is the markdown text I generated based on the image content:", instead you should directly output markdown.
3. Content should not be contained within ```markdown ```.
4. Use $$ $$ for paragraph formulas, use $ $ for inline formulas.
5. Ignore long straight lines, and ignore page numbers.
Again, do not explain or output irrelevant text, directly output the content from the image.
"""

DEFAULT_EXTRACT_RECT_PROMPT = """The image contains some areas marked with red boxes and names ({name}). Replace the area with the name of the area strictly in format <img src="area_name" />.
"""

DEFAULT_RECT_PROMPT = """The name of the image is {name}. You need to determine the type of the area and output the corresponding markdown syntax. There are 4 types of areas (the types are listed from top to bottom in order of priority):
1. If the area is a table, and the table can be converted to markdown, use the markdown table format to insert it into the output content, otherwise use the image format to insert it into the output content.
2. If the area is a formula, use the $$ $$ format to insert it into the output content.
3. If the area contains only text, output the text content directly.
4. If the area is a image, use the image format to insert it into the output content.
Do not explain or output irrelevant text, directly output the content from the image. For example, it is strictly forbidden to output examples like "Here is the markdown text I generated based on the image content:", instead you should directly output markdown.
The image format is ![](img_name), and img_name must be exactly the name of the image.
"""

DEFAULT_ROLE_PROMPT = """You are a PDF document parser, using markdown and latex syntax to output the content of the image.
"""


def _is_near(rect1, rect2, distance: float = 20) -> bool:
    """
    Check if two rectangles are close to each other, if the distance between them is less than the target distance.
    @param rect1: rectangle 1
    @param rect2: rectangle 2
    @param distance: target distance
    @return: whether they are close to each other
    """
    return rect1.buffer(0.1).distance(rect2.buffer(0.1)) < distance


def _is_horizontal_near(rect1, rect2, distance: float = 100) -> bool:
    """
    Check if two rectangles are horizontally close to each other, if one of them is a horizontal line.
    @param rect1: rectangle 1
    @param rect2: rectangle 2
    @param distance: target distance
    @return: whether they are horizontally close to each other
    """
    result = False
    if abs(rect1.bounds[3] -
           rect1.bounds[1]) < 0.1 or abs(rect2.bounds[3] -
                                         rect2.bounds[1]) < 0.1:
        if abs(rect1.bounds[0] -
               rect2.bounds[0]) < 0.1 and abs(rect1.bounds[2] -
                                              rect2.bounds[2]) < 0.1:
            result = abs(rect1.bounds[3] - rect2.bounds[3]) < distance
    return result


def _union_rects(rect1, rect2):
    """
    Merge two rectangles.
    @param rect1: rectangle 1
    @param rect2: rectangle 2
    @return: merged rectangle
    """
    return sg.box(*(rect1.union(rect2).bounds))


def _merge_rects(rect_list: List,
                 distance: float = 20,
                 horizontal_distance: Optional[float] = None):
    """
    Merge rectangles in the list, if the distance between them is less than the target distance.
    @param rect_list: list of rectangles
    @param distance: target distance
    @param horizontal_distance: target horizontal distance
    @return: merged rectangles
    """
    merged = True
    while merged:
        merged = False
        new_rect_list = []
        while rect_list:
            rect = rect_list.pop(0)
            for other_rect in rect_list:
                if _is_near(rect, other_rect, distance) or (
                        horizontal_distance and _is_horizontal_near(
                            rect, other_rect, horizontal_distance)):
                    rect = _union_rects(rect, other_rect)
                    rect_list.remove(other_rect)
                    merged = True
            new_rect_list.append(rect)
        rect_list = new_rect_list
    return rect_list


def _adsorb_rects_to_rects(source_rects, target_rects, distance: float = 10):
    """
    When the distance is less than the target distance, adsorb a group of rectangles to another group of rectangles.
    @param source_rects: source rectangles
    @param target_rects: target rectangles
    @param distance: target distance
    @return: adsorbed source rectangles and target rectangles
    """
    new_source_rects = []
    for text_area_rect in source_rects:
        adsorbed = False
        for index, rect in enumerate(target_rects):
            if _is_near(text_area_rect, rect, distance):
                rect = _union_rects(text_area_rect, rect)
                target_rects[index] = rect
                adsorbed = True
                break
        if not adsorbed:
            new_source_rects.append(text_area_rect)
    return new_source_rects, target_rects


def _parse_rects(page):
    """
    Parse the drawings in the page, and merge adjacent rectangles.
    @param page: page
    @return: list of rectangles
    """

    #  extract the content of the drawings
    drawings = page.get_drawings()

    #  ignore horizontal lines shorter than 30
    def is_short_line(x):
        virticle_size = abs(x['rect'][3] - x['rect'][1])
        horizontal_size = abs(x['rect'][2] - x['rect'][0])
        return virticle_size < 1 and horizontal_size < 30

    drawings = [drawing for drawing in drawings if not is_short_line(drawing)]

    #  convert to shapely rectangles
    rect_list = [sg.box(*drawing['rect']) for drawing in drawings]

    #  extract image areas
    images = page.get_image_info()
    image_rects = [sg.box(*image['bbox']) for image in images]

    #  merge drawings and images
    rect_list += image_rects

    merged_rects = _merge_rects(rect_list,
                                distance=10,
                                horizontal_distance=100)
    merged_rects = [
        rect for rect in merged_rects
        if explain_validity(rect) == 'Valid Geometry'
    ]

    #  separate large and small text areas: large text areas are merged, small text areas are merged near
    is_large_content = lambda x: (len(x[4]) / max(1, len(x[4].split('\n')))
                                  ) > 5
    small_text_area_rects = [
        sg.box(*x[:4]) for x in page.get_text('blocks')
        if not is_large_content(x)
    ]
    large_text_area_rects = [
        sg.box(*x[:4]) for x in page.get_text('blocks') if is_large_content(x)
    ]
    _, merged_rects = _adsorb_rects_to_rects(
        large_text_area_rects, merged_rects,
        distance=0.1)  # completely intersect
    _, merged_rects = _adsorb_rects_to_rects(small_text_area_rects,
                                             merged_rects,
                                             distance=5)  # close

    #  merge again
    merged_rects = _merge_rects(merged_rects, distance=10)

    #  filter out small rectangles
    merged_rects = [
        rect for rect in merged_rects if rect.bounds[2] -
        rect.bounds[0] > 20 and rect.bounds[3] - rect.bounds[1] > 20
    ]

    return [rect.bounds for rect in merged_rects]


def _parse_pdf_to_images(pdf_path: str, output_dir='./'):
    """
    Parse the PDF file to images, and save to the output directory.
    @param pdf_path: PDF file path
    @param output_dir: output directory
    @return: list of image information (image path, list of rectangle image paths)
    """

    # Open the PDF file
    pdf_document = fitz.open(pdf_path)
    image_infos: List[Tuple[str, List[str]]] = []

    for page_index in range(len(pdf_document)):
        page: Any = pdf_document[page_index]

        logging.info(f'parse page: {page_index}')

        rect_images: List[str] = []
        rects = _parse_rects(page)

        for index, rect in enumerate(rects):
            fitz_rect = fitz.Rect(rect)

            # Save the page as an image
            pix = page.get_pixmap(clip=fitz_rect, matrix=fitz.Matrix(4, 4))
            rect_name = f'{page_index}_{index}.png'
            rect_image = os.path.join(output_dir, rect_name)
            pix.save(rect_image)
            logging.info(f'save rect image: {rect_image}')
            rect_images.append(rect_image)

            # Draw red rectangles on the page
            big_fitz_rect = fitz.Rect(fitz_rect.x0 - 1, fitz_rect.y0 - 1,
                                      fitz_rect.x1 + 1, fitz_rect.y1 + 1)

            # Solid rectangle
            page.draw_rect(big_fitz_rect,
                           color=(1, 0, 0),
                           fill=(1, 0, 0),
                           width=1)

            # Draw rectangle area (solid)
            # Write the index name of the rectangle in the upper left corner of the rectangle, add some offset
            text_x = fitz_rect.x0 + 2
            text_y = fitz_rect.y0 + 10
            text_rect = fitz.Rect(text_x, text_y - 9, text_x + 80, text_y + 2)

            # Draw white background rectangle
            page.draw_rect(text_rect, color=(1, 1, 1), fill=(1, 1, 1))

            # Insert text with white background
            page.insert_text((text_x, text_y),
                             rect_name,
                             fontsize=10,
                             color=(1, 0, 0))

        page_image_with_rects = page.get_pixmap(matrix=fitz.Matrix(3, 3))
        page_image = os.path.join(output_dir, f'{page_index}.png')
        page_image_with_rects.save(page_image)
        logging.info(f'save page image: {page_image}')
        image_infos.append((page_image, rect_images))

    pdf_document.close()
    return image_infos


def _remove_backticks(content: str) -> str:
    """
    Delete the ``` code block wrappers from the content.
    """
    # Pattern to match ```language at the start and ``` at the end
    pattern = r'^```[a-zA-Z]*\n?(.*?)\n?```$'
    match = re.search(pattern, content.strip(), re.DOTALL)

    if match:
        # Return the content inside the code block
        return match.group(1)

    # If no complete code block found, try to remove partial backticks
    # Remove starting ```language
    content = re.sub(r'^```[a-zA-Z]*\n?', '', content.strip())

    # Remove ending ```
    if content.endswith('```'):
        content = content[:-3].rstrip()

    return content


@weave.op()
def _process_page(
        index: int,  #
        client: OpenAI,
        model: str,
        image_info: Tuple[str, List[str]],
        prompt: str,
        extract_prompt: str,
        role_prompt: str):

    try:
        page_image, rect_images = image_info
        local_prompt = prompt
        if rect_images:
            rect_names = [
                re.split(r'[\\/]', rect_image)[-1]
                for rect_image in rect_images
            ]
            local_prompt += extract_prompt.format(name=', '.join(rect_names))

        with open(page_image, "rb") as image_file:
            image_base64 = base64.b64encode(image_file.read()).decode('utf-8')

        logging.info(f'process page image: {page_image}')

        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "system",
                "content": role_prompt
            }, {
                "role":
                "user",
                "content": [{
                    "type": "text",
                    "text": local_prompt
                }, {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}"
                    }
                }]
            }])

        #  check if response.choices is None
        if not response.choices:
            logging.error(
                f'Error: Empty choices in API response for page {index+1}: {response}'
            )
            return index, f"Error: Empty choices in API response for page {index+1}"

        content = response.choices[0].message.content
        return index, content or ""
    except Exception as e:
        #  capture all exceptions and return error information
        logging.error(f'Error processing page {index+1}: {str(e)}')
        return index, f"Error processing page {index+1}: {str(e)}"


@weave.op()
def _process_rects(
        client: OpenAI,  #
        model: str,
        rect_image: str,
        rect_prompt: str,
        role_prompt: str):

    try:
        with open(rect_image, "rb") as image_file:
            image_base64 = base64.b64encode(image_file.read()).decode('utf-8')

        rect_name = re.split(r'[\\/]', rect_image)[-1]
        rect_prompt = rect_prompt.format(name=rect_name)

        logging.info(f'process rect image: {rect_image}')

        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "system",
                "content": role_prompt
            }, {
                "role":
                "user",
                "content": [{
                    "type": "text",
                    "text": rect_prompt
                }, {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}"
                    }
                }]
            }])

        #  check if response.choices is None
        if not response.choices:
            logging.error(
                f'Error: Empty choices in API response for rect {rect_name}: {response}'
            )
            return rect_name, f"Error: Empty choices in API response for rect {rect_name}"

        content = response.choices[0].message.content
        return rect_name, content or ""
    except Exception as e:
        #  capture all exceptions and return error information
        logging.error(f'Error processing rect {rect_name}: {str(e)}')
        return rect_name, f"Error processing rect {rect_name}: {str(e)}"


@weave.op()
def parse_pdf(pdf_path: str,
              output_dir: str = './',
              api_key: Optional[str] = None,
              base_url: Optional[str] = None,
              model: str = 'gpt-4o',
              gpt_worker: int = 1,
              prompt=DEFAULT_PROMPT,
              extract_prompt=DEFAULT_EXTRACT_RECT_PROMPT,
              rect_prompt=DEFAULT_RECT_PROMPT,
              role_prompt=DEFAULT_ROLE_PROMPT,
              delete=True) -> Tuple[str, List[str]]:
    """
    Parse the PDF file to markdown file.
    @param pdf_path: PDF file path
    @param output_dir: output directory
    @param api_key: OpenAI API key
    @param base_url: OpenAI base URL
    @param model: OpenAI model
    @param gpt_worker: number of GPT workers
    @param prompt: prompt
    @param rect_prompt: rectangle prompt
    @param delete: whether to delete the intermediate images
    @return: parsed markdown content, list of rectangle image paths
    """

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[
                            logging.FileHandler(f'{output_dir}/parse.log',
                                                encoding='utf-8'),
                            logging.StreamHandler()
                        ])

    # parse page images
    image_infos = _parse_pdf_to_images(pdf_path, output_dir=output_dir)

    contents = [""] * len(image_infos)
    client = OpenAI(api_key=api_key, base_url=base_url)

    with weave.ThreadPoolExecutor(max_workers=gpt_worker) as executor:
        futures = [
            executor.submit(
                _process_page,  #
                index,
                client,
                model,
                image_info,
                prompt,
                extract_prompt,
                role_prompt) for index, image_info in enumerate(image_infos)
        ]
        for future in as_completed(futures):
            index, text = future.result()
            text = _remove_backticks(text)
            contents[index] = text

    md_content = '\n\n'.join(contents)

    # parse rect images
    all_rect_images: List[str] = []
    for _, rect_images in image_infos:
        all_rect_images.extend(rect_images)

    with weave.ThreadPoolExecutor(max_workers=gpt_worker) as executor:
        futures = [
            executor.submit(
                _process_rects,  #
                client,
                model,
                rect_image,
                rect_prompt,
                role_prompt) for rect_image in all_rect_images
        ]
        for future in as_completed(futures):
            rect_name, text = future.result()
            text = _remove_backticks(text)
            md_content = md_content.replace(f'<img src="{rect_name}" />', text)

    #  save the parsed markdown file
    output_path = os.path.join(output_dir, 'output.md')
    with open(output_path, 'w', encoding='utf-8') as f:
        logging.info(f'save markdown file: {output_path}')
        f.write(md_content)

    #  delete the intermediate images
    for page_image, _ in image_infos:
        if delete and os.path.exists(page_image):
            logging.info(f'delete page image: {page_image}')
            os.remove(page_image)

    #  delete the intermediate rect images
    img_srcs = re.findall(r'!\[.*?\]\(([^)]+)\)', md_content)
    img_srcs = [os.path.join(output_dir, img_src) for img_src in img_srcs]
    removed_rect_images = set(all_rect_images) - set(img_srcs)
    for rect_image in removed_rect_images:
        if delete and os.path.exists(rect_image):
            logging.info(f'delete rect image: {rect_image}')
            os.remove(rect_image)

    return md_content, all_rect_images


if __name__ == "__main__":
    import argparse
    import shutil
    import dotenv

    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_path", type=str)
    parser.add_argument("-o", "--output_dir", type=str, default="test_output")
    args = parser.parse_args()

    dotenv.load_dotenv()
    api_key = os.getenv('OPENROUTER_API_KEY')
    base_url = os.getenv('OPENROUTER_BASEE_URL')
    model = os.getenv('OPENROUTER_MODEL') or 'gpt-4o'

    shutil.rmtree(args.output_dir, ignore_errors=True)

    weave.init(project_name='gptpdf')

    content, image_paths = parse_pdf(
        args.pdf_path,
        output_dir=args.output_dir,
        api_key=api_key,
        base_url=base_url,
        model=model,
        gpt_worker=6,
    )
