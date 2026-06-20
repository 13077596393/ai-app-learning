from html.parser import (
    HTMLParser,
)  # 导入 Python 标准库里的 HTMLParser，用来解析 HTML 标签
from pathlib import Path  # 导入 Path，用来更方便地处理文件路径


class SimpleHTMLTextExtractor(
    HTMLParser
):  # 定义一个简单的 HTML 文本提取器，用来从 HTML 中提取纯文本。SimpleHTMLTextExtractor 这个类，继承 HTMLParser 的功能。
    def __init__(self):  # 定义初始化方法，创建解析器对象时自动执行
        super().__init__()  # 调用父类 HTMLParser 的初始化方法，保证 HTML 解析器正常工作
        self.text_parts = []  # 创建列表，用来保存从 HTML 中提取出来的文本片段

    def handle_data(
        self, data
    ):  # 当 HTMLParser 解析到普通文本内容时，会自动调用这个方法
        cleaned_data = data.strip()  # 去掉当前文本片段前后的空白字符
        if cleaned_data:  # 判断清理后的文本是否不为空
            self.text_parts.append(
                cleaned_data
            )  # 如果文本不为空，就添加到 text_parts 列表中

    def get_text(self) -> str:  # 定义获取完整纯文本的方法
        return "\n".join(self.text_parts)  # 把所有文本片段用换行符拼接成完整文本并返回


def parse_txt(
    file_path: str,
) -> str:  # 定义解析 txt 文件的函数，接收文件路径并返回纯文本
    return Path(file_path).read_text(
        encoding="utf-8"
    )  # 使用 utf-8 编码读取 txt 文件内容并返回


def parse_md(
    file_path: str,
) -> str:  # 定义解析 Markdown 文件的函数，接收文件路径并返回纯文本
    return Path(file_path).read_text(
        encoding="utf-8"
    )  # Markdown 本质也是文本文件，所以这里直接读取文件内容


def parse_html(
    file_path: str,
) -> str:  # 定义解析 HTML 文件的函数，接收文件路径并返回去除标签后的纯文本
    html_content = Path(file_path).read_text(
        encoding="utf-8"
    )  # 使用 utf-8 编码读取 HTML 文件内容
    parser = SimpleHTMLTextExtractor()  # 创建 HTML 文本提取器对象
    parser.feed(html_content)  # 把 HTML 内容交给解析器处理
    return parser.get_text()  # 返回从 HTML 中提取出来的纯文本


def parse_pdf(
    file_path: str,
) -> str:  # 定义解析 PDF 文件的函数，接收 PDF 文件路径并返回纯文本
    import fitz  # 在函数内部导入 pymupdf 的 fitz 模块，避免项目启动时因为依赖问题直接失败

    text_parts = []  # 创建列表，用来保存每一页 PDF 提取出来的文本

    with fitz.open(file_path) as pdf_document:  # 打开 PDF 文件，并在使用结束后自动关闭
        for page_index in range(
            len(pdf_document)
        ):  # 遍历 PDF 的每一页，page_index 从 0 开始
            page = pdf_document[page_index]  # 根据页码索引获取当前 PDF 页面对象
            page_text = page.get_text(
                "text"
            ).strip()  # 从当前页面提取普通文本，并去掉前后空白字符
            if page_text:  # 判断当前页面是否提取到了文本
                text_parts.append(
                    page_text
                )  # 如果当前页有文本，就添加到 text_parts 列表中

    return "\n\n".join(text_parts)  # 把所有页面文本用两个换行拼接成完整文本并返回


def parse_docx(
    file_path: str,
) -> str:  # 定义解析 Word docx 文件的函数，接收 docx 文件路径并返回纯文本
    from docx import (
        Document as DocxDocument,
    )  # 在函数内部导入 python-docx 的 Document，避免和我们自己的 Document 模型冲突

    docx_document = DocxDocument(file_path)  # 打开 Word 文档并创建 docx 文档对象

    text_parts = []  # 创建列表，用来保存 Word 中每一段非空文本

    for paragraph in docx_document.paragraphs:  # 遍历 Word 文档里的所有段落
        paragraph_text = paragraph.text.strip()  # 获取当前段落文本，并去掉前后空白字符
        if paragraph_text:  # 判断当前段落文本是否不为空
            text_parts.append(
                paragraph_text
            )  # 如果段落不为空，就添加到 text_parts 列表中

    return "\n".join(text_parts)  # 把所有段落文本用换行符拼接成完整文本并返回


def parse_document(
    file_path: str, file_type: str
) -> str:  # 定义统一文档解析入口，根据文件类型调用不同解析函数
    normalized_file_type = (
        file_type.lower().strip()
    )  # 把文件类型转成小写并去掉前后空白，避免 PDF 和 pdf 判断不一致

    if normalized_file_type == "txt":  # 判断当前文件是否是 txt 文本文件
        return parse_txt(file_path)  # 调用 txt 解析函数并返回纯文本

    if normalized_file_type == "md":  # 判断当前文件是否是 Markdown 文件
        return parse_md(file_path)  # 调用 Markdown 解析函数并返回纯文本

    if normalized_file_type == "html":  # 判断当前文件是否是 HTML 文件
        return parse_html(file_path)  # 调用 HTML 解析函数并返回纯文本

    if normalized_file_type == "pdf":  # 判断当前文件是否是 PDF 文件
        return parse_pdf(file_path)  # 调用 PDF 解析函数并返回纯文本

    if normalized_file_type == "docx":  # 判断当前文件是否是 Word docx 文件
        return parse_docx(file_path)  # 调用 Word 解析函数并返回纯文本

    raise ValueError(
        f"暂不支持解析该文件类型：{file_type}"
    )  # 如果文件类型不在支持范围内，就主动抛出错误
