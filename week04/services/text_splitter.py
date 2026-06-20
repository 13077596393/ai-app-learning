from typing import List  # 导入 List 类型，用来表示函数返回的是字符串列表


def split_text(
    text: str, chunk_size: int = 500, chunk_overlap: int = 100
) -> List[str]:  # 定义文本切块函数，接收原始文本、每块长度和重叠长度
    if not text:  # 判断传入的文本是否为空字符串或者 None
        return []  # 如果文本为空，直接返回空列表，避免后续切分报错

    if chunk_size <= 0:  # 判断 chunk_size 是否小于等于 0
        raise ValueError(
            "chunk_size 必须大于 0"
        )  # 如果 chunk_size 不合法，主动抛出错误提醒开发者

    if chunk_overlap < 0:  # 判断 chunk_overlap 是否小于 0
        raise ValueError("chunk_overlap 不能小于 0")  # 如果重叠长度小于 0，主动抛出错误

    if chunk_overlap >= chunk_size:  # 判断重叠长度是否大于或等于每块长度
        raise ValueError(
            "chunk_overlap 必须小于 chunk_size"
        )  # 如果重叠长度太大，切块时会无法正常向前推进

    cleaned_text = text.strip()  # 去掉文本开头和结尾的空白字符，让切块结果更干净

    if not cleaned_text:  # 判断清理后的文本是否为空
        return []  # 如果清理后为空，返回空列表

    chunks: List[str] = []  # 创建 chunks 列表，用来保存切分出来的每一个文本块

    start = 0  # 定义当前 chunk 的起始位置，第一次从文本第 0 个字符开始

    text_length = len(cleaned_text)  # 计算清理后文本的总长度

    while start < text_length:  # 只要起始位置还没有超过文本长度，就继续切分
        end = start + chunk_size  # 计算当前 chunk 的结束位置

        chunk = cleaned_text[start:end]  # 根据起始位置和结束位置截取当前文本块

        chunk = chunk.strip()  # 去掉当前文本块前后的空白字符

        if chunk:  # 判断当前 chunk 是否不是空字符串
            chunks.append(chunk)  # 如果 chunk 有内容，就添加到 chunks 列表中

        if end >= text_length:  # 判断当前结束位置是否已经到达或超过全文末尾
            break  # 如果已经切到最后，就退出循环

        start = end - chunk_overlap  # 计算下一个 chunk 的起始位置，并保留一部分重叠内容

    return chunks  # 返回切分后的所有文本块列表
