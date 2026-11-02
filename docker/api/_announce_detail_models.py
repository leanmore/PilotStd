"""公告明细接口的 Pydantic 响应模型（从 announce_detail 拆出，控制 G-010 文件规模）。"""

from pydantic import BaseModel


class AnnouncementRecordPageItem(BaseModel):
    """分页记录条目：公告记录表的原始列（空值原样保留）。"""

    id: int
    row_index: int | None
    standard_number: str
    std_name: str | None
    publish_date: str | None
    implement_date: str | None
    expiry_date: str | None
    superseded_by: str | None
    status: str | None
    language: str | None
    foreign_name: str | None
    source_site: str


# 公告记录分页：total/page/page_size 与 items
class AnnouncementRecordsPageResponse(BaseModel):
    """分页记录响应：当前页条目、总数、页码、每页条数与是否还有更多。"""

    items: list[AnnouncementRecordPageItem]
    total: int
    page: int
    pageSize: int
    hasMore: bool


class AnnouncementHeaderItem(BaseModel):
    """公告头：公告号、标题、发布日期、来源链接、站点名、正文与来源标识。"""

    id: int
    announce_no: str
    title: str
    publish_date: str
    source_url: str
    attachment_url: str
    site_name: str
    content: str
    source: str
    source_type: str


class AnnouncementRecordItem(BaseModel):
    """详情页记录条目：标准号、名称、日期、替代关系、状态与匹配元数据。"""

    id: int
    row_index: int
    standard_number: str
    std_name: str
    publish_date: str
    implement_date: str
    expiry_date: str
    superseded_by: str
    status: str
    confidence: float
    source_type: str
    created_at: str
    updated_at: str


# 公告详情：头信息 + 明细行
class AnnouncementDetailResponse(BaseModel):
    """公告详情响应：公告头、标准记录列表与解析状态。"""

    announcement: AnnouncementHeaderItem
    records: list[AnnouncementRecordItem]
    parse_status: str


class AnnouncementRecordLiteItem(BaseModel):
    """轻量记录条目：仅表格渲染必需的字段，不含匹配元数据。"""

    id: int
    row_index: int
    standard_number: str
    std_name: str
    publish_date: str
    implement_date: str
    expiry_date: str
    superseded_by: str
    status: str


class AnnouncementDetailLiteResponse(BaseModel):
    """轻量公告详情响应：与完整版同构，记录字段更少。"""

    announcement: AnnouncementHeaderItem
    records: list[AnnouncementRecordLiteItem]
    parse_status: str


class AnnouncementSourceHeaderItem(BaseModel):
    """按公告号查询到的公告头：来源站点、公告号与标题。"""

    source_site: str
    announce_no: str
    title: str


# 解析应答：解析结果与统计
class AnnouncementParseResponse(BaseModel):
    """触发附件解析的结果：已解析则给出记录数，开始解析则给出公告号。"""

    status: str
    record_count: int | None = None
    announce_no: str | None = None


class AnnouncementReparseResponse(BaseModel):
    """重新抓取公告详情的结果：状态、公告号与本次解析出的记录数。"""

    status: str
    announce_no: str
    records: int


class AnnouncementParseStatusResponse(BaseModel):
    """公告解析状态：完成或待解析，以及已入库记录数。"""

    status: str
    record_count: int


# 批量确认：状态、批准数与错误
class AnnouncementBatchApproveResponse(BaseModel):
    """批量确认入库结果：完成状态、批准数量与错误明细。"""

    status: str
    approved_count: int
    errors: list[str]
