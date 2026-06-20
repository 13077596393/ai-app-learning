import pytest  # 导入 pytest，用来测试异常抛出场景

from services.text_splitter import (
    split_text,
)  # 导入文本切分函数，作为当前测试文件的被测对象


def test_split_text_should_return_empty_list_when_text_is_empty():  # 测试空字符串是否返回空列表
    chunks = split_text("")  # 调用 split_text，传入空字符串

    assert chunks == []  # 断言返回结果必须是空列表


def test_split_text_should_return_empty_list_when_text_only_has_spaces():  # 测试只有空格和换行的文本是否返回空列表
    chunks = split_text("   \n   ")  # 调用 split_text，传入只有空白字符的文本

    assert chunks == []  # 断言清理后没有内容，所以返回空列表


def test_split_text_should_split_text_by_chunk_size():  # 测试普通文本是否能按 chunk_size 正常切分
    text = "abcdefghij"  # 构造长度为 10 的测试文本

    chunks = split_text(  # 调用文本切分函数
        text=text,  # 传入测试文本
        chunk_size=4,  # 每个 chunk 最多 4 个字符
        chunk_overlap=0,  # 不设置重叠内容
    )  # 得到切分结果

    assert chunks == ["abcd", "efgh", "ij"]  # 断言文本被切成 4、4、2 三段


def test_split_text_should_keep_overlap_between_chunks():  # 测试 chunk 之间是否保留重叠内容
    text = "abcdefghij"  # 构造长度为 10 的测试文本

    chunks = split_text(  # 调用文本切分函数
        text=text,  # 传入测试文本
        chunk_size=4,  # 每个 chunk 最多 4 个字符
        chunk_overlap=2,  # 相邻 chunk 保留 2 个字符重叠
    )  # 得到切分结果

    assert chunks == [
        "abcd",
        "cdef",
        "efgh",
        "ghij",
    ]  # 断言每个 chunk 和上一个 chunk 有 2 个字符重叠


def test_split_text_should_raise_error_when_chunk_size_is_zero():  # 测试 chunk_size 为 0 时是否抛出异常
    with pytest.raises(ValueError):  # 断言下面代码必须抛出 ValueError
        split_text(  # 调用文本切分函数
            text="hello",  # 传入正常文本
            chunk_size=0,  # 设置非法 chunk_size
            chunk_overlap=0,  # 设置重叠为 0
        )  # 结束函数调用


def test_split_text_should_raise_error_when_chunk_overlap_is_negative():  # 测试 chunk_overlap 为负数时是否抛出异常
    with pytest.raises(ValueError):  # 断言下面代码必须抛出 ValueError
        split_text(  # 调用文本切分函数
            text="hello",  # 传入正常文本
            chunk_size=5,  # 设置合法 chunk_size
            chunk_overlap=-1,  # 设置非法负数 overlap
        )  # 结束函数调用


def test_split_text_should_raise_error_when_overlap_greater_than_or_equal_chunk_size():  # 测试 overlap 大于等于 chunk_size 时是否抛出异常
    with pytest.raises(ValueError):  # 断言下面代码必须抛出 ValueError
        split_text(  # 调用文本切分函数
            text="hello",  # 传入正常文本
            chunk_size=5,  # 设置每块长度为 5
            chunk_overlap=5,  # 设置 overlap 等于 chunk_size，这是非法情况
        )  # 结束函数调用
