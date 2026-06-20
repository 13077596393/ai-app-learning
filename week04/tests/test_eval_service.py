from schemas import RagCitation  # 导入 RagCitation，用来构造假的引用来源数据

from services.eval_service import (  # 从 eval_service 中导入要测试的评测函数
    check_expected_document_hit,  # 导入文档命中检查函数
    check_expected_keywords,  # 导入关键词命中检查函数
    split_expected_keywords,  # 导入关键词切分函数
)  # 结束导入


def make_citation(  # 定义测试辅助函数，用来快速创建 RagCitation
    document_name: str = "企业制度知识库测试文档.txt",  # 默认文档名
    content: str = "试用期员工离职需要提前 3 天通知公司。",  # 默认引用完整内容
    preview: str = "试用期员工离职需要提前 3 天通知公司。",  # 默认引用预览内容
) -> RagCitation:  # 返回 RagCitation 对象
    return RagCitation(  # 创建并返回 RagCitation
        source_index=1,  # 设置资料编号为 1
        chunk_id=1,  # 设置 chunk ID
        document_id=1,  # 设置文档 ID
        document_name=document_name,  # 设置文档名称
        chunk_index=0,  # 设置 chunk 序号
        vector_score=0.8,  # 设置向量分数
        keyword_score=0.6,  # 设置关键词分数
        hybrid_score=0.74,  # 设置混合检索分数
        final_score=0.74,  # 设置兼容旧字段的最终分数
        rerank_score=0.86,  # 设置 Rerank 精排分数
        content=content,  # 设置完整引用内容
        preview=preview,  # 设置引用预览内容
    )  # 结束 RagCitation 创建


def test_split_expected_keywords_should_support_chinese_comma():  # 测试关键词字符串是否支持中文逗号
    keywords = split_expected_keywords(  # 调用关键词切分函数
        "试用期，离职，提前"  # 传入使用中文逗号分隔的关键词字符串
    )  # 得到关键词列表

    assert keywords == [  # 断言中文逗号可以被正确识别
        "试用期",  # 第一个关键词
        "离职",  # 第二个关键词
        "提前",  # 第三个关键词
    ]  # 结束断言


def test_check_expected_keywords_should_pass_when_answer_hits_all_keywords():  # 测试答案命中全部关键词时是否通过
    citation = make_citation()  # 创建一条假的引用来源

    hit, matched, missing = check_expected_keywords(  # 调用关键词命中检查函数
        expected_keywords="试用期,离职,提前",  # 设置期望关键词
        answer="根据资料，试用期员工离职需要提前通知公司。[资料 1]",  # 构造命中全部关键词的答案
        citations=[citation],  # 传入引用来源列表
    )  # 得到检查结果

    assert hit is True  # 断言关键词检查通过
    assert matched == ["试用期", "离职", "提前"]  # 断言三个关键词都被命中
    assert missing == []  # 断言没有缺失关键词


def test_check_expected_keywords_should_use_citation_content_too():  # 测试关键词可以从 citation 内容里命中
    citation = make_citation(  # 创建一条引用来源
        content="试用期员工离职需要提前 3 天通知公司。",  # 引用内容包含关键词 3 天
        preview="试用期员工离职需要提前 3 天通知公司。",  # 引用预览也包含关键词 3 天
    )  # 结束引用创建

    hit, matched, missing = check_expected_keywords(  # 调用关键词检查函数
        expected_keywords="试用期,离职,3 天",  # 设置期望关键词，其中 3 天 主要来自 citation
        answer="根据资料，试用期员工离职应提前通知公司。[资料 1]",  # 答案本身没有写 3 天
        citations=[citation],  # 传入引用来源
    )  # 得到检查结果

    assert hit is True  # 断言关键词检查通过，因为 citation 内容补足了关键词
    assert matched == ["试用期", "离职", "3 天"]  # 断言所有关键词都被命中
    assert missing == []  # 断言没有缺失关键词


def test_check_expected_keywords_should_report_missing_keywords():  # 测试缺少关键词时是否返回 missing_keywords
    citation = make_citation(  # 创建一条引用来源
        content="正式员工离职通常需要提前 30 天提交申请。",  # 引用内容不包含试用期和 3 天
        preview="正式员工离职通常需要提前 30 天提交申请。",  # 引用预览同样不包含试用期和 3 天
    )  # 结束引用创建

    hit, matched, missing = check_expected_keywords(  # 调用关键词检查函数
        expected_keywords="试用期,离职,3 天",  # 设置期望关键词
        answer="正式员工离职需要提前 30 天申请。[资料 1]",  # 构造只命中离职的答案
        citations=[citation],  # 传入引用来源
    )  # 得到检查结果

    assert hit is False  # 断言关键词检查失败
    assert matched == ["离职"]  # 断言只命中了离职
    assert missing == ["试用期", "3 天"]  # 断言缺少试用期和 3 天


def test_check_expected_keywords_should_pass_when_expected_keywords_is_empty():  # 测试没有配置关键词时是否默认通过
    citation = make_citation()  # 创建一条假的引用来源

    hit, matched, missing = check_expected_keywords(  # 调用关键词检查函数
        expected_keywords="",  # 不配置期望关键词
        answer="知识库中没有找到足够相关的内容。",  # 构造任意答案
        citations=[citation],  # 传入引用来源
    )  # 得到检查结果

    assert hit is True  # 断言没有关键词时默认通过
    assert matched == []  # 断言没有命中关键词列表
    assert missing == []  # 断言没有缺失关键词列表


def test_check_expected_document_hit_should_pass_when_document_name_matches():  # 测试 citation 文档名命中期望文档名时是否通过
    citation = make_citation(  # 创建一条引用来源
        document_name="企业制度知识库测试文档.txt"  # 设置实际引用文档名
    )  # 结束引用创建

    hit = check_expected_document_hit(  # 调用文档命中检查函数
        expected_document_name="企业制度知识库测试文档",  # 设置期望文档名，不带 .txt 也应该能匹配
        citations=[citation],  # 传入引用来源
    )  # 得到检查结果

    assert hit is True  # 断言文档命中通过


def test_check_expected_document_hit_should_fail_when_document_name_not_matches():  # 测试 citation 文档名不匹配时是否失败
    citation = make_citation(  # 创建一条引用来源
        document_name="报销制度.txt"  # 设置实际引用文档名
    )  # 结束引用创建

    hit = check_expected_document_hit(  # 调用文档命中检查函数
        expected_document_name="员工手册",  # 设置不匹配的期望文档名
        citations=[citation],  # 传入引用来源
    )  # 得到检查结果

    assert hit is False  # 断言文档命中失败


def test_check_expected_document_hit_should_pass_when_expected_document_name_is_empty():  # 测试没有配置期望文档名时是否默认通过
    citation = make_citation(  # 创建一条引用来源
        document_name="任意文档.txt"  # 设置任意文档名
    )  # 结束引用创建

    hit = check_expected_document_hit(  # 调用文档命中检查函数
        expected_document_name="",  # 不配置期望文档名
        citations=[citation],  # 传入引用来源
    )  # 得到检查结果

    assert hit is True  # 断言没有期望文档名时默认通过
