from datetime import datetime  # 导入 datetime，用来设置评测用例创建和更新时间
from typing import Literal  # 导入 Literal，用来限制权限参数只能是 view 或 write


from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)  # 导入 FastAPI 路由、依赖注入和异常
from sqlmodel import Session, select  # 导入数据库会话和查询构造函数

from database import get_session  # 导入数据库会话依赖
from models import (
    KnowledgeBase,
    RagEvalCase,
    RagEvalRun,
    RagEvalResult,
)  # 导入知识库和评测相关模型
from routers.users import get_current_user  # 导入当前用户依赖，用来做登录鉴权
from schemas import (  # 导入评测相关请求体和响应体
    RagEvalBatchRunResponse,  # 批量评测运行结果响应体
    RagEvalCaseCreate,  # 创建评测用例请求体
    RagEvalCaseListResponse,  # 评测用例列表响应体
    RagEvalCaseResponse,  # 评测用例响应体
    RagEvalResultResponse,  # 历史单题评测结果响应体
    RagEvalRunDetailResponse,  # 某次评测运行详情响应体
    RagEvalRunListResponse,  # 历史评测运行列表响应体
    RagEvalRunResponse,  # 历史评测运行记录响应体
    RagEvalSingleRunResponse,  # 单条评测运行结果响应体
)
from services.eval_service import (  # 导入评测业务逻辑服务
    run_eval_case_logic,  # 运行单条评测用例
    save_eval_run_results,  # 保存批量评测运行结果
)
from services.project_permission_service import (  # 导入项目空间权限判断函数
    can_view_project,  # 判断当前用户是否可以查看项目空间
    can_write_project,  # 判断当前用户是否可以写入项目空间
)  # 项目权限函数导入结束

router = APIRouter(  # 创建评测模块路由对象
    prefix="/knowledge-bases",  # 所有评测接口都挂在知识库下面
    tags=["RAG 评测"],  # Swagger 分组名称
)


def get_user_knowledge_base(  # 获取并校验当前用户是否有权限访问知识库
    session: Session,  # 数据库会话
    knowledge_base_id: int,  # 知识库 ID
    current_user,  # 当前登录用户
    permission: Literal[
        "view", "write"
    ] = "view",  # 权限类型：view 表示查看，write 表示写入或运行评测
) -> KnowledgeBase:  # 返回知识库对象
    statement = select(KnowledgeBase).where(  # 构建查询知识库的 SQL 语句
        KnowledgeBase.id == knowledge_base_id  # 按知识库 ID 查询
    )  # 结束查询语句构建

    knowledge_base = session.exec(statement).first()  # 执行查询并取第一条结果

    if knowledge_base is None:  # 如果知识库不存在
        raise HTTPException(  # 抛出 HTTP 异常
            status_code=404,  # 404 表示资源不存在
            detail="知识库不存在",  # 返回错误提示
        )  # 结束异常抛出

    if permission == "view":  # 如果当前接口只需要查看权限
        if not can_view_project(  # 判断当前用户是否可以查看该知识库所属项目空间
            session=session,  # 传入数据库会话
            project_id=knowledge_base.project_id,  # 使用知识库的 project_id 判断项目权限
            user=current_user,  # 传入当前登录用户
        ):  # 权限判断结束
            raise HTTPException(  # 如果没有查看权限
                status_code=404,  # 返回 404，避免泄露知识库是否存在
                detail="知识库不存在或无权访问",  # 返回错误提示
            )  # 结束异常抛出

    if permission == "write":  # 如果当前接口需要写入权限
        if not can_write_project(  # 判断当前用户是否可以写入该知识库所属项目空间
            session=session,  # 传入数据库会话
            project_id=knowledge_base.project_id,  # 使用知识库的 project_id 判断项目权限
            user=current_user,  # 传入当前登录用户
        ):  # 权限判断结束
            raise HTTPException(  # 如果没有写入权限
                status_code=403,  # 403 表示没有权限
                detail="没有权限操作该知识库评测功能",  # 返回错误提示
            )  # 结束异常抛出

    return knowledge_base  # 返回知识库对象


def get_eval_case_or_404(  # 查询评测用例，如果不存在则抛出 404
    session: Session,  # 数据库会话
    knowledge_base_id: int,  # 知识库 ID
    case_id: int,  # 评测用例 ID
) -> RagEvalCase:  # 返回评测用例对象
    statement = select(RagEvalCase).where(  # 构建查询评测用例的 SQL 语句
        RagEvalCase.id == case_id,  # 按评测用例 ID 查询
        RagEvalCase.knowledge_base_id == knowledge_base_id,  # 确保用例属于当前知识库
    )  # 结束查询语句构建

    eval_case = session.exec(statement).first()  # 执行查询并取第一条结果

    if eval_case is None:  # 如果评测用例不存在
        raise HTTPException(status_code=404, detail="评测用例不存在")  # 返回 404

    return eval_case  # 返回评测用例对象


def build_eval_case_response(
    eval_case: RagEvalCase,
) -> RagEvalCaseResponse:  # 把数据库评测用例转换成响应模型
    return RagEvalCaseResponse(  # 返回评测用例响应对象
        id=eval_case.id or 0,  # 返回评测用例 ID
        knowledge_base_id=eval_case.knowledge_base_id,  # 返回知识库 ID
        question=eval_case.question,  # 返回评测问题
        expected_answer=eval_case.expected_answer,  # 返回参考答案
        expected_keywords=eval_case.expected_keywords,  # 返回期望关键词
        expected_document_name=eval_case.expected_document_name,  # 返回期望文档名
        should_refuse=eval_case.should_refuse,  # 返回是否期望拒答
        created_at=eval_case.created_at,  # 返回创建时间
        updated_at=eval_case.updated_at,  # 返回更新时间
    )  # 结束响应对象创建


def build_eval_run_response(
    eval_run: RagEvalRun,
) -> RagEvalRunResponse:  # 把数据库评测运行记录转换成响应模型
    return RagEvalRunResponse(  # 返回评测运行响应对象
        id=eval_run.id or 0,  # 返回评测运行 ID
        knowledge_base_id=eval_run.knowledge_base_id,  # 返回知识库 ID
        total=eval_run.total,  # 返回总题数
        passed_count=eval_run.passed_count,  # 返回通过数量
        failed_count=eval_run.failed_count,  # 返回失败数量
        hit_rate=eval_run.hit_rate,  # 返回命中率
        created_at=eval_run.created_at,  # 返回创建时间
    )  # 结束响应对象创建


def build_eval_result_response(
    eval_result: RagEvalResult,
) -> RagEvalResultResponse:  # 把数据库单题结果转换成响应模型
    return RagEvalResultResponse(  # 返回单题评测结果响应对象
        id=eval_result.id or 0,  # 返回结果 ID
        eval_run_id=eval_result.eval_run_id,  # 返回所属评测运行 ID
        eval_case_id=eval_result.eval_case_id,  # 返回所属评测用例 ID
        knowledge_base_id=eval_result.knowledge_base_id,  # 返回知识库 ID
        question=eval_result.question,  # 返回问题快照
        expected_answer=eval_result.expected_answer,  # 返回参考答案快照
        actual_answer=eval_result.actual_answer,  # 返回实际答案
        should_refuse=eval_result.should_refuse,  # 返回是否期望拒答
        actual_refused=eval_result.actual_refused,  # 返回是否实际拒答
        confidence_level=eval_result.confidence_level,  # 返回置信度
        expected_keywords=eval_result.expected_keywords,  # 返回期望关键词
        matched_keywords=eval_result.matched_keywords,  # 返回命中关键词字符串
        missing_keywords=eval_result.missing_keywords,  # 返回缺失关键词字符串
        hit_expected_keywords=eval_result.hit_expected_keywords,  # 返回关键词命中结果
        expected_document_name=eval_result.expected_document_name,  # 返回期望文档名
        hit_expected_document=eval_result.hit_expected_document,  # 返回文档命中结果
        citation_valid=eval_result.citation_valid,  # 返回引用校验结果
        passed=eval_result.passed,  # 返回是否通过
        notes=eval_result.notes,  # 返回评测说明
        citations_json=eval_result.citations_json,  # 返回 citations JSON 快照
        created_at=eval_result.created_at,  # 返回创建时间
    )  # 结束响应对象创建


@router.post(  # 注册创建 RAG 评测用例接口
    "/{knowledge_base_id}/eval-cases",  # 接口路径
    response_model=RagEvalCaseResponse,  # 指定响应模型
)
def create_rag_eval_case(  # 创建评测用例接口函数
    knowledge_base_id: int,  # 知识库 ID
    case_data: RagEvalCaseCreate,  # 请求体数据
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user=Depends(get_current_user),  # 注入当前登录用户
):  # 结束函数参数定义
    get_user_knowledge_base(
        session,
        knowledge_base_id,
        current_user,
        permission="write",  # 创建评测用例属于写入操作，admin/member 可以，viewer 不可以
    )  # 校验知识库权限

    question = case_data.question.strip()  # 清理问题前后空白

    if not question:  # 如果问题为空
        raise HTTPException(status_code=400, detail="评测问题不能为空")  # 返回 400

    eval_case = RagEvalCase(  # 创建评测用例数据库对象
        knowledge_base_id=knowledge_base_id,  # 设置知识库 ID
        question=question,  # 设置评测问题
        expected_answer=case_data.expected_answer.strip(),  # 设置参考答案
        expected_keywords=case_data.expected_keywords.strip(),  # 设置期望关键词
        expected_document_name=case_data.expected_document_name.strip(),  # 设置期望文档名
        should_refuse=case_data.should_refuse,  # 设置是否期望拒答
        created_at=datetime.utcnow(),  # 设置创建时间
        updated_at=datetime.utcnow(),  # 设置更新时间
    )  # 结束评测用例对象创建

    session.add(eval_case)  # 加入数据库会话
    session.commit()  # 提交事务
    session.refresh(eval_case)  # 刷新对象，获取数据库生成的 ID

    return build_eval_case_response(eval_case)  # 返回响应模型，避免直接返回 ORM 对象


@router.get(  # 注册查询评测用例列表接口
    "/{knowledge_base_id}/eval-cases",  # 接口路径
    response_model=RagEvalCaseListResponse,  # 指定响应模型
)
def list_rag_eval_cases(  # 查询评测用例列表接口函数
    knowledge_base_id: int,  # 知识库 ID
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user=Depends(get_current_user),  # 注入当前登录用户
):  # 结束函数参数定义
    get_user_knowledge_base(
        session,
        knowledge_base_id,
        current_user,
        permission="view",
    )  # 校验知识库权限

    statement = select(RagEvalCase).where(  # 构建查询当前知识库评测用例的 SQL
        RagEvalCase.knowledge_base_id == knowledge_base_id  # 按知识库 ID 过滤
    )  # 结束查询语句构建

    eval_cases = session.exec(statement).all()  # 执行查询
    items = [
        build_eval_case_response(eval_case) for eval_case in eval_cases
    ]  # 转换成响应模型列表

    return RagEvalCaseListResponse(total=len(items), items=items)  # 返回列表响应


@router.post(  # 注册运行单条评测用例接口
    "/{knowledge_base_id}/eval-cases/{case_id}/run",  # 接口路径
    response_model=RagEvalSingleRunResponse,  # 指定响应模型
)
def run_single_rag_eval_case(  # 运行单条评测接口函数
    knowledge_base_id: int,  # 知识库 ID
    case_id: int,  # 评测用例 ID
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user=Depends(get_current_user),  # 注入当前登录用户
):  # 结束函数参数定义
    get_user_knowledge_base(
        session,
        knowledge_base_id,
        current_user,
        permission="write",  # 运行评测属于写入/成本操作，admin/member 可以，viewer 不可以
    )  # 校验知识库权限
    eval_case = get_eval_case_or_404(
        session, knowledge_base_id, case_id
    )  # 查询评测用例

    return run_eval_case_logic(  # 调用 service 层运行评测
        session=session,  # 传入数据库会话
        knowledge_base_id=knowledge_base_id,  # 传入知识库 ID
        eval_case=eval_case,  # 传入评测用例对象
    )  # 结束评测运行


@router.post(  # 注册批量运行评测用例接口
    "/{knowledge_base_id}/eval-cases/run-all",  # 接口路径
    response_model=RagEvalBatchRunResponse,  # 指定响应模型
)
def run_all_rag_eval_cases(  # 批量运行评测接口函数
    knowledge_base_id: int,  # 知识库 ID
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user=Depends(get_current_user),  # 注入当前登录用户
):  # 结束函数参数定义
    get_user_knowledge_base(
        session,
        knowledge_base_id,
        current_user,
        permission="write",  # 批量运行评测属于写入/成本操作，admin/member 可以，viewer 不可以
    )  # 校验知识库权限

    statement = select(RagEvalCase).where(  # 构建查询当前知识库所有评测用例的 SQL
        RagEvalCase.knowledge_base_id == knowledge_base_id  # 按知识库 ID 过滤
    )  # 结束查询语句构建

    eval_cases = session.exec(statement).all()  # 查询所有评测用例
    results: list[RagEvalSingleRunResponse] = []  # 创建评测结果列表

    for eval_case in eval_cases:  # 遍历每条评测用例
        result = run_eval_case_logic(  # 调用 service 层运行单条评测
            session=session,  # 传入数据库会话
            knowledge_base_id=knowledge_base_id,  # 传入知识库 ID
            eval_case=eval_case,  # 传入评测用例对象
        )  # 结束单条评测运行
        results.append(result)  # 保存当前评测结果

    total = len(results)  # 统计总数量
    passed_count = sum(1 for result in results if result.passed)  # 统计通过数量
    failed_count = total - passed_count  # 计算失败数量
    hit_rate = passed_count / total if total > 0 else 0  # 计算命中率

    save_eval_run_results(  # 保存本次批量评测历史记录
        session=session,  # 传入数据库会话
        knowledge_base_id=knowledge_base_id,  # 传入知识库 ID
        results=results,  # 传入所有单题结果
    )  # 结束保存

    return RagEvalBatchRunResponse(  # 返回批量评测响应
        knowledge_base_id=knowledge_base_id,  # 返回知识库 ID
        total=total,  # 返回总题数
        passed_count=passed_count,  # 返回通过数
        failed_count=failed_count,  # 返回失败数
        hit_rate=hit_rate,  # 返回命中率
        items=results,  # 返回单题明细
    )  # 结束响应对象创建


@router.get(  # 注册查询历史评测运行列表接口
    "/{knowledge_base_id}/eval-runs",  # 接口路径
    response_model=RagEvalRunListResponse,  # 指定响应模型
)
def list_rag_eval_runs(  # 查询历史评测运行列表接口函数
    knowledge_base_id: int,  # 知识库 ID
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user=Depends(get_current_user),  # 注入当前登录用户
):  # 结束函数参数定义
    get_user_knowledge_base(
        session,
        knowledge_base_id,
        current_user,
        permission="view",
    )  # 校验知识库权限

    statement = (  # 构建查询历史运行记录的 SQL
        select(RagEvalRun)  # 查询 RagEvalRun 表
        .where(RagEvalRun.knowledge_base_id == knowledge_base_id)  # 按知识库 ID 过滤
        .order_by(RagEvalRun.created_at.desc())  # 按创建时间倒序排列
    )  # 结束查询语句构建

    eval_runs = session.exec(statement).all()  # 执行查询
    items = [
        build_eval_run_response(eval_run) for eval_run in eval_runs
    ]  # 转换成响应模型列表

    return RagEvalRunListResponse(total=len(items), items=items)  # 返回历史运行列表


@router.get(  # 注册查看某次评测运行详情接口
    "/{knowledge_base_id}/eval-runs/{run_id}",  # 接口路径
    response_model=RagEvalRunDetailResponse,  # 指定响应模型
)
def get_rag_eval_run_detail(  # 查看某次评测详情接口函数
    knowledge_base_id: int,  # 知识库 ID
    run_id: int,  # 评测运行 ID
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user=Depends(get_current_user),  # 注入当前登录用户
):  # 结束函数参数定义
    get_user_knowledge_base(
        session,
        knowledge_base_id,
        current_user,
        permission="view",
    )  # 校验知识库权限

    run_statement = select(RagEvalRun).where(  # 构建查询评测运行记录的 SQL
        RagEvalRun.id == run_id,  # 按 run_id 查询
        RagEvalRun.knowledge_base_id == knowledge_base_id,  # 确保属于当前知识库
    )  # 结束查询语句构建

    eval_run = session.exec(run_statement).first()  # 查询评测运行记录

    if eval_run is None:  # 如果评测运行不存在
        raise HTTPException(status_code=404, detail="评测运行记录不存在")  # 返回 404

    result_statement = (  # 构建查询本次评测单题结果的 SQL
        select(RagEvalResult)  # 查询 RagEvalResult 表
        .where(  # 添加过滤条件
            RagEvalResult.eval_run_id == run_id,  # 按评测运行 ID 过滤
            RagEvalResult.knowledge_base_id == knowledge_base_id,  # 按知识库 ID 过滤
        )  # 结束过滤条件
        .order_by(RagEvalResult.id.asc())  # 按 ID 正序排列
    )  # 结束查询语句构建

    eval_results = session.exec(result_statement).all()  # 查询单题结果列表
    run_response = build_eval_run_response(eval_run)  # 转换评测运行总览响应
    result_items = [
        build_eval_result_response(eval_result) for eval_result in eval_results
    ]  # 转换单题结果响应列表

    return RagEvalRunDetailResponse(  # 返回评测详情响应
        run=run_response,  # 返回运行总览
        results=result_items,  # 返回单题结果列表
    )  # 结束响应对象创建
