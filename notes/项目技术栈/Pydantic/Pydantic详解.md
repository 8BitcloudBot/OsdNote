# Pydantic 详解

> Python 生态中最主流的数据验证库，Python 3.6+ 类型提示的实践标杆。
> 核心信条：**用类型注解做数据校验，在运行时保证数据形状正确。**

---

## 总体概览

### 是什么

Pydantic 是一个基于 Python 类型提示（Type Hints）的**运行时数据验证库**。

你在代码里写 `name: str`，Pydantic 就会在创建对象时自动检查传入的 `name` 是不是真正的字符串、是否满足约束条件。它把 "类型注解" 从**仅供 IDE 和 linter 阅读的标注**变成了**程序自身就能执行的校验规则**。

```python
# 没有 Pydantic：类型注解只是注释
class User:
    def __init__(self, name: str, age: int):
        self.name = name  # 传入 123 也不会报错
        self.age = age

# 有 Pydantic：类型注解是执行规则
class User(BaseModel):
    name: str        # 传入 123 -> ValidationError
    age: int         # 传入 "abc" -> ValidationError
```

### 有什么用

Pydantic 解决了软件工程中一个极其常见的问题：**数据边界不可信**。

在任何一个系统中，数据会在这些边界流动：用户输入 → API 接口 → 业务逻辑 → 数据库 → 外部服务。每一次跨越边界，数据的"形状"都可能被篡改、遗漏或污染。Pydantic 就是在这些边界上做检查的守门员：

| 场景 | 没有 Pydantic 的后果 | Pydantic 的解法 |
|------|---------------------|----------------|
| 用户提交表单 | 手写 `if not isinstance(...)` 层层校验，漏一个就出 bug | 声明式模型定义，自动校验所有字段 |
| LLM 返回 JSON | 假设输出一定合法，结果字段缺失导致程序崩溃 | `PydanticOutputParser` 二次验证，不合法就抛异常 |
| 配置文件加载 | YAML/JSON 里的类型错误在运行时才暴露 | 加载时就校验，早失败早发现 |
| 数据库层写入 | 脏数据入库，修复成本极高 | 写入前校验，拒绝不合规数据 |
| API 响应序列化 | 敏感字段漏排除、日期格式不统一 | `model_dump(exclude=...)` 精确控制输出 |

### 组成

Pydantic 由三个层次构成，从内到外：

```
┌─────────────────────────────────────────────┐
│  第三层：生态集成                             │
│  FastAPI / LangChain / SQLModel / Datetime   │
│  这些框架以 Pydantic 为核心，扩展具体场景      │
├─────────────────────────────────────────────┤
│  第二层：高级能力                             │
│  TypeAdapter / ConfigDict / 泛型 / 序列化     │
│  解决非 BaseModel 类型、全局配置、性能等需求   │
├─────────────────────────────────────────────┤
│  第一层：核心模型                             │
│  BaseModel / Field / Validator               │
│  定义数据形状 + 声明约束 + 自定义校验          │
│  pydantic-core（Rust 引擎）执行实际校验        │
└─────────────────────────────────────────────┘
```

**第一层 - 核心模型**：`BaseModel` 是所有模型的基类，`Field` 提供字段级约束，`@field_validator` / `@model_validator` 提供自定义校验逻辑。底层由 Rust 编写的 `pydantic-core` 引擎执行实际的类型转换和校验，保证性能。

**第二层 - 高级能力**：`TypeAdapter` 将校验能力扩展到非 BaseModel 类型（如 `List[int]`），`ConfigDict` 统一管理模型行为（严格模式、不可变、额外字段策略），泛型支持和灵活的序列化控制（`model_dump` / `model_dump_json`）构成完整的数据处理管线。

**第三层 - 生态集成**：FastAPI 用 Pydantic 做请求体验证和 OpenAPI 文档生成，LangChain/LlamaIndex 用 PydanticOutputParser 约束 LLM 输出格式，SQLModel 用 Pydantic 模型直接映射数据库表。这些框架让 Pydantic 从一个数据验证库变成了整个 Python 生态的数据契约标准。

---

## 一、Pydantic V2 概览

Pydantic V2（2023 年发布）相比 V1 核心变化：

| 维度 | V1 | V2 |
|------|----|----|
| 底层引擎 | Python 实现 | **Rust** 核心 (`pydantic-core`) |
| 性能 | 基线 | 5-50x 更快 |
| 模型定义 | `BaseModel` | `BaseModel`（兼容） |
| 校验方法 | `__init__` 内建 | 新的 Rust 验证流程 |
| 泛型 | 有限支持 | 原生支持 |
| 类型适配器 | ❌ | ✅ `TypeAdapter` |

---

## 二、核心用法

### 2.1 基础模型定义

```python
from pydantic import BaseModel, Field       # BaseModel: 所有模型的基类; Field: 字段约束
from typing import List, Optional            # 标准类型提示
from datetime import datetime                # Pydantic 原生支持 datetime 校验

class User(BaseModel):
    """
    定义一个用户数据模型。
    只需写类型注解，Pydantic 自动处理：
      - 类型校验：传入的值必须是 int/str/List 等
      - 类型转换：传入 '123' 自动转 123（宽松模式下）
      - 缺省处理：未传 signup_ts 时使用 None
    """
    id: int                                   # 必填。传入 "123" 会被自动转为 123
    name: str                                 # 必填。传入 42 会被自动转为 "42"
    email: str                                # 必填。Pydantic 不做格式校验（除非用 EmailStr）
    signup_ts: Optional[datetime] = None      # 可选，默认 None。传入 "2024-01-01T00:00:00" 自动转 datetime
    tags: List[str] = []                      # 可选，默认空列表。默认值是共享引用，Pydantic 会深拷贝

# 传入 "123"（字符串），但因 Pydantic 宽松模式默认开启，自动执行 int("123")
user = User(id="123", name="Alice", email="alice@example.com")

print(user.model_dump())
# model_dump() 将 Pydantic 实例转回普通字典，等价于 V1 的 .dict()
# -> {"id": 123, "name": "Alice", "email": "alice@example.com", "signup_ts": None, "tags": []}
```

### 2.2 Field 的高级配置

```python
from pydantic import BaseModel, Field, field_validator
# Field: 在字段类型注解之外附加约束、元信息、别名等配置
# field_validator: 对单个字段做自定义业务校验

class Product(BaseModel):
    """
    Field(..., min_length=1, max_length=100)
      第一个参数"..."表示必填（没有默认值）；
      min_length/max_length 对字符串生效，等价于 len(name) 检查
    """
    name: str = Field(
        ...,                                # ... = Ellipsis，表示此字段必填、无默认值
        min_length=1,                       # 校验 len(name) >= 1
        max_length=100,                     # 校验 len(name) <= 100
        description="商品名称"               # 描述信息，用于生成 JSON Schema
    )

    """
    Field(gt=0, le=99999.99)
      gt=0: 值必须大于 0 (greater than)
      le=99999.99: 值必须小于等于 99999.99 (less or equal)
      类似约束还有: ge(>=), lt(<), multiple_of(整数倍)
    """
    price: float = Field(
        gt=0,                              # 必须大于 0
        le=99999.99,                        # 必须 <= 99999.99
        description="价格"
    )

    """
    alias="desc": 指定一个别名。
      外部传入时可使用 desc=xxx，内部通过 description 访问。
      典型场景：对接外部 API 字段命名不同（如 snake_case vs camelCase）。
    """
    description: str = Field(
        default="",                         # 可选，默认为空字符串
        alias="desc"                        # 外部输入用 "desc"，代码内部用 .description
    )

    """
    frozen=True: 使字段不可变。
      实例化后尝试修改会触发 ValidationError。
      作用类似 @property read-only，但发生在数据层。
    """
    category: str = Field(
        default="general",                  # 可选，默认值 "general"
        frozen=True                         # 冻结字段：赋值后不可修改
    )

    # ========== 自定义字段校验器 ==========
    # 注意：V1 用 @validator，V2 改用 @field_validator
    # 必须加 @classmethod，第一个参数 cls，第二个参数是要校验的值
    @field_validator("name")
    @classmethod
    def name_must_be_meaningful(cls, v: str) -> str:
        """
        v: 用户传入的 name 值（已通过类型转换，确保是 str）
        返回值: 校验通过后实际存储的值（可修改）
        异常: raise ValueError 即校验失败

        注意: 校验顺序 = 先内置类型检查 -> 再 Field 约束 -> 最后 @field_validator
        """
        if v.strip() == "":
            raise ValueError("name cannot be blank")  # 抛异常 = 校验失败
        return v.strip()                              # 返回处理后的值来替代原始值
```

### 2.3 嵌套模型

```python
from pydantic import BaseModel

class Address(BaseModel):
    """
    地址子模型。嵌套使用时，Address 自动校验内层字典的字段。
    """
    city: str                             # 必填
    street: str                           # 必填
    zip_code: str                         # 必填

class Company(BaseModel):
    """
    address: Address 表示嵌套校验。
    外部传入时 address 可以是一个 dict，Pydantic 自动递归解析成 Address 实例。
    """
    name: str                             # 必填
    address: Address                      # 嵌套模型：传入 dict 自动转 Address 对象

# 注意：address 传入的是字典 {"city": ...}，不是 Address 实例
# Pydantic 会自动递归调用 Address(**{"city": "SF", ...}) 完成嵌套校验
company = Company(
    name="OpenAI",
    address={
        "city": "SF",
        "street": "123 St",
        "zip_code": "94105"
    }
)

print(company.model_dump())
# model_dump() 默认递归展开嵌套对象，输出:
# {"name": "OpenAI", "address": {"city": "SF", "street": "123 St", "zip_code": "94105"}}

# 访问嵌套属性：
print(company.address.city)   # -> "SF"
# 类型提示 IDE 也能正确推导，这是 Pydantic 对比普通 dict 的核心优势
```

### 2.4 类型适配器（V2 新增）

```python
from pydantic import TypeAdapter
from typing import List

# ========== TypeAdapter 是什么？ ==========
# V1 中，想要校验一个 "非 BaseModel 的类型"（如 int、List[str]），必须手工写逻辑。
# V2 的 TypeAdapter 把 BaseModel 的校验能力 "适配" 到任意类型上。

# 示例 1：校验基本类型
int_adapter = TypeAdapter(int)
# validate_python("42")：传入 Python 对象 "42"，校验它能否转为 int
# 宽松模式下 "42" -> 42，相当于 int("42") 再校验
result = int_adapter.validate_python("42")      # -> 42
# 等价于: int("42")，但额外享受 Pydantic 的错误消息格式和约束

# 示例 2：校验复杂泛型（嵌套验证的关键）
list_of_ints = TypeAdapter(List[int])
# 传入 ["1", "2", "3"]，每个元素逐一执行 int(x) 校验
result = list_of_ints.validate_python(["1", "2", "3"])  # -> [1, 2, 3]

# 示例 3：校验 JSON 字符串（真实场景最常见）
json_input = '{"name": "Alice", "age": "30"}'
# validate_json() 先做 JSON.parse，再递归校验
user_adapter = TypeAdapter(User)                     # 假设 User 是之前定义的 BaseModel
user = user_adapter.validate_json(json_input)        # -> User(name="Alice", age=30)

# 总结: TypeAdapter 让 Pydantic V2 的校验能力覆盖到所有类型，
# 不再是 BaseModel 子类的特权。
```

---

## 三、校验机制

### 3.1 校验流程

```
输入数据
    |
    v
pydantic-core（Rust 实现的核心引擎）
    |
    v 解析 JSON / Python 对象
类型转换（如 "123" -> 123, "true" -> True）
    | 失败 -> ValidationError（含详细错误路径和原因）
    v
@field_validator（字段级自定义校验，按字段依次执行）
    | 每个字段可独立抛 ValueError
    v
@model_validator（模型级跨字段校验，在所有字段校验完后执行）
    |
    v
输出 Pydantic 实例
```

关键特点：
- **短路**：类型转换失败就不会进入 field_validator
- **顺序**：field_validator 按定义顺序执行 -> model_validator
- **合并错误**：所有校验完成后一次性抛出 ValidationError，包含所有字段的错误

### 3.2 字段校验器

```python
from pydantic import BaseModel, field_validator
from typing import List

class Order(BaseModel):
    """
    订单模型，演示 @field_validator 的完整用法。
    """
    items: List[str]                      # 商品列表
    total: float                          # 订单总价

    # ========== @field_validator 基础用法 ==========
    # 修饰器参数 "total": 绑定到 total 字段
    # 模式: after（默认）— 在 Pydantic 内置校验完成后执行
    # 其他模式: before（在内置校验前执行）、wrap（包裹内置校验）
    @field_validator("total")
    @classmethod
    def positive_total(cls, v: float) -> float:
        """
        v: 已经过类型转换的 total 值（字符串已转 float）
        校验失败：raise ValueError("reason")
        校验成功：return v（可以返回修改后的值）

        注意：如果返回的类型与注解不一致（如返回 str），会触发额外校验
        """
        if v <= 0:
            raise ValueError("total must be positive")  # 抛异常 -> 校验失败
        return v  # 返回原始值，不做修改

    # ========== 校验器绑定多个字段 ==========
    # field_validator("items") 可叠加多个字段，如 ("items", "names", ...)
    @field_validator("items")
    @classmethod
    def check_items(cls, v: List[str]) -> List[str]:
        """
        校验 items 不能为空列表。
        注意：field_validator 默认是 "after" 模式，
        即在类型校验（确保 v 是 List[str]）之后执行。
        """
        if not v:
            raise ValueError("at least one item required")  # 空列表 -> 拒绝
        return v  # 返回清洗后的数据（可做去重、排序等）
```

### 3.3 模型校验器

```python
from pydantic import BaseModel, model_validator
from datetime import datetime

class Booking(BaseModel):
    """
    预订模型。需要 start < end 的跨字段约束。
    这种约束无法用 @field_validator（它只看单字段），必须用 @model_validator。
    """
    start: datetime                       # 开始时间
    end: datetime                         # 结束时间

    # ========== @model_validator 模式说明 ==========
    # mode="after": 所有字段校验 + 类型转换完成后执行
    #   self 是已部分构建的 Booking 实例，可任意访问所有字段
    # mode="before": 在字段校验前执行，收到的是原始 dict
    #   较少使用，多用于预处理输入数据
    @model_validator(mode="after")
    def check_dates(self) -> "Booking":
        """
        mode="after": self 是 Booking 实例（只有全部字段通过后才会进入 after 模式）

        check 逻辑：开始时间必须在结束时间之前
        失败：raise ValueError
        成功：return self（必须返回模型实例，不能返回 None）

        为什么不用 @field_validator？
        - start 校验时不知道 end 的值（反之亦然）
        - field_validator 是单字段视角，model_validator 是全字段视角
        """
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self  # 必须返回 self，否则实例构造中断

    # ========== 补充：mode="before" 的典型用法 ==========
    # @model_validator(mode="before")
    # @classmethod
    # def preprocess(cls, data: dict) -> dict:
    #     """ 在字段校验之前先处理原始数据 """
    #     if isinstance(data, str):  # 如果传入的是 JSON 字符串
    #         import json
    #         data = json.loads(data)
    #     return data
```

---

## 四、序列化

### 4.1 model_dump（dict 化）

```python
# .model_dump() 是 V2 中 .dict() 的替代品
# 将 Pydantic 实例转为普通 Python 字典

user = User(id=1, name="Alice", email="a@b.com", password="secret")

user.model_dump()                         # -> {"id": 1, "name": "Alice", ...}
# 默认递归展开所有嵌套模型，输出纯 Python 原生类型

user.model_dump(exclude={"password"})     # -> 排除敏感字段
# exclude: 集合/字典，指定要排除的字段名
# 等价效果: include={"id", "name", "email"} 只保留指定字段

user.model_dump(by_alias=True)            # -> 使用别名作为 key
# 如果定义字段时指定了 alias="desc"，此处 key 变为 "desc" 而非 "description"
# 典型场景：将内部 snake_case 转为外部 API 的 camelCase

user.model_dump(mode="json")              # -> 所有值转为 JSON 兼容类型
# 默认 mode="python"：datetime 保持 datetime 对象
# mode="json"：datetime -> ISO 字符串，Decimal -> float，确保可 json.dumps()

# 典型应用：API 响应层
# return user.model_dump(exclude={"password"}, mode="json", by_alias=True)
```

### 4.2 model_dump_json（JSON 字符串）

```python
# .model_dump_json() 是 .json() 的 V2 替代品
# 直接返回 JSON 字符串，省去手动 import json

user.model_dump_json()
# -> '{"id":1,"name":"Alice","email":"a@b.com",...}'
# 等价于 json.dumps(user.model_dump(mode="json"))

user.model_dump_json(indent=2)
# 带缩进的美化输出，适合调试、日志、配置文件持久化
# indent=2 表示每层缩进 2 空格

# 额外参数：
# user.model_dump_json(exclude={"password"}, by_alias=True, round_trip=True)
# round_trip=True: 确保 JSON 反序列化后与原始对象一致（如保持浮点数精度）
```

### 4.3 ConfigDict 配置

```python
from pydantic import BaseModel, ConfigDict
# ConfigDict: V2 替代 V1 的内部 Config 类，用于配置模型行为

# 辅助函数：用于 alias_generator，将 snake_case 转 camelCase
def to_camel(field_name: str) -> str:
    """snake_case -> camelCase 的转换函数"""
    parts = field_name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])

class Config(BaseModel):
    """
    演示常见 ConfigDict 配置项。
    注意：V2 用 model_config = ConfigDict(...)，不再是内部 Config 类。
    """
    model_config = ConfigDict(
        # === 不可变性 ===
        frozen=True,                        # 实例化后所有字段只读
        # user.name = "new" -> ValidationError
        # 等效于每个字段都加 frozen=True

        # === 额外字段处理 ===
        extra="forbid",                     # 拒绝未定义的字段
        # "ignore": 静默忽略
        # "allow": 存入 __pydantic_extra__ 字典
        # 生产环境建议 "forbid" 防止拼写错误导致静默数据丢失

        # === 别名 ===
        alias_generator=to_camel,           # 自动为所有字段生成 camelCase 别名
        # 如果字段名是 user_name，自动生成别名 "userName"
        # 与手动指定 alias 叠加（手动优先级更高）

        # === 别名行为 ===
        populate_by_name=True,              # 赋值时可使用原始名称或别名
        # True: User(user_name="xxx") 和 User(userName="xxx") 都行
        # False: 只能用别名（需配合 alias_generator）
    )

    user_name: str
    email_address: str
    is_active: bool

# 使用示例：
obj = Config(user_name="Alice", email_address="a@b.com", is_active=True)
print(obj.user_name)                    # -> "Alice"

# populate_by_name=True 允许用原名序列化：
print(obj.model_dump(by_alias=False))
# -> {"user_name": "Alice", "email_address": "a@b.com", "is_active": True}

# 用别名序列化：
print(obj.model_dump(by_alias=True))
# -> {"userName": "Alice", "emailAddress": "a@b.com", "isActive": True}
```

---

## 五、Pydantic 在 RAG 生态中的角色

### 5.1 LangChain Output Parsers

```python
from pydantic import BaseModel, Field
from typing import List
from langchain_core.output_parsers import PydanticOutputParser
# PydanticOutputParser: LangChain 提供的 "LLM 输出 -> Pydantic 对象" 桥梁
# 核心原理:
#   1. 读取 Pydantic 模型 -> 生成 JSON Schema
#   2. 把 JSON Schema 注入到 Prompt 中，告诉 LLM "请按这个格式输出"
#   3. LLM 返回 JSON 字符串 -> PydanticOutputParser 解析成 Pydantic 实例

class MovieReview(BaseModel):
    """
    定义一个电影评论数据结构。
    注意 Field(description=xxx) 中的 description 非常重要：
    它们会作为自然语言描述出现在 LLM 看到的 Prompt 中，
    直接影响 LLM 输出的字段含义理解。
    """
    title: str = Field(
        description="电影名称"           # 这句中文会原样写入 Prompt
    )
    rating: float = Field(
        description="评分，1-10",         # 描述越具体，LLM 输出越稳定
        ge=0, le=10                      # Pydantic 层面再加一层保险
    )
    summary: str = Field(
        description="电影简介，不超过100字"
    )
    keywords: List[str] = Field(
        description="关键词列表，3-5个"
    )

# ========== PydanticOutputParser 内部发生了什么 ==========
parser = PydanticOutputParser(pydantic_object=MovieReview)

# Step 1: 调用 MovieReview.model_json_schema() 生成 JSON Schema
# {
#   "title": {"type": "string", "description": "电影名称"},
#   "rating": {"type": "number", "description": "评分，1-10"},
#   ...
# }

# Step 2: get_format_instructions() 将 Schema 包裹进预设模板
format_instructions = parser.get_format_instructions()
# 实际输出类似:
# "请将输出格式化为符合以下 JSON Schema 的 JSON 对象。
#  {\"properties\": {\"title\": {\"description\": \"电影名称\", ...}}}"

# Stage 3: Prompt 组装
# prompt = f"{user_query}\n{format_instructions}"
# -> LLM 看到明确的结构要求

# Stage 4: 解析返回的 JSON
# parser.parse(llm_output)
#   内部调用 MovieReview.model_validate(json_dict)
#   如果 LLM 返回的 JSON 缺字段/类型不对 -> 抛 OutputParserException

# 完整调用链：
# chain = prompt | llm | parser
# result = chain.invoke({"text": "请解析《盗梦空间》的评论"})
# result 的类型是 MovieReview，而非字典！
# result.title, result.rating 都有 IDE 类型提示
```

### 5.2 FastAPI 请求体验证

```python
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

class Item(BaseModel):
    """
    FastAPI 中定义请求体（Request Body）的标准方式。
    FastAPI 检测到 route 参数类型是 BaseModel 子类时，
    自动：
      1. 从请求 body 读取 JSON
      2. 用 Pydantic 校验并转成 Item 实例
      3. 如果校验失败，自动返回 422 Unprocessable Entity
      4. 自动生成 OpenAPI Schema（Swagger 文档）
    """
    name: str                             # 必填
    price: float                          # 必填
    tax: Optional[float] = None           # 可选。请求体中可省略

@app.post("/items/")
async def create_item(item: Item):
    """
    item: Item 类型注解 -> FastAPI 自动解析请求体
    无需手动调用 Item(...) 或 try/except，FastAPI 全自动

    返回值: Python dict -> FastAPI 自动转 JSON 响应
    """
    return item.model_dump()

# ========== 请求示例 ==========
# POST /items/
# Body: {"name": "Keyboard", "price": 299.99}
# -> item.tax 为 None（missing_field，但非必填，不会报错）
# Response: {"name": "Keyboard", "price": 299.99, "tax": null}

# POST /items/
# Body: {"name": "", "price": -1}
# -> Pydantic 校验失败（空字符串 + 价格 <=0）
# -> FastAPI 自动返回 422 + 详细错误
```

### 5.3 LLM 结构化输出的万能桥梁

```
LLM 原始输出（非结构化文本）
      |
      v
PydanticOutputParser / Function Calling
      | 解析 + 校验
      v
Pydantic 实例（类型安全 + 字段提示）
      |
      v
数据库 ORM 写入 / REST API 响应 / 前端渲染 / 下游服务
```

为什么说 Pydantic 是"万能桥梁"？

```
类型系统里的每个角色都理解 Pydantic：
  - LLM 理解它 -> 通过 Schema 指导输出
  - Python 理解它 -> IDE 提示 + 运行时校验
  - FastAPI 理解它 -> 自动校验 + 文档 + 序列化
  - ORM 理解它 -> SQLModel、Beanie 等以 Pydantic 为核心
  - JSON 理解它 -> model_dump_json() 直接输出
```

---

## 六、Function Calling + Pydantic 实战

```python
from pydantic import BaseModel, Field
# Function Calling（Tool Calling）是现代 LLM 的关键能力。
# 核心机制：定义工具 -> LLM 选择工具 -> 代码执行工具 -> 结果送回 LLM
# Pydantic 的作用：**用 BaseModel 来定义 tools 的 JSON Schema**

class WeatherParams(BaseModel):
    """
    定义 "获取天气" 这个工具的入参结构。
    Pydantic 自动将其转换为 LLM 理解的 JSON Schema。

    关键：类的文档字符串和 Field(description=)
    会直接成为 LLM 看到的工具描述，影响 LLM 能否正确选择此工具。
    """
    location: str = Field(
        description="城市名称，如北京、上海、广州"
    )
    unit: str = Field(
        default="celsius",
        description="温度单位：celsius（摄氏）或 fahrenheit（华氏）"
    )

# ========== model_json_schema() 输出工具定义 ==========
tool_schema = WeatherParams.model_json_schema()
# 输出：
# {
#   "description": "获取天气的函数参数",
#   "type": "object",
#   "properties": {
#     "location": {"type": "string", "description": "城市名称..."},
#     "unit": {"type": "string", "default": "celsius",
#              "description": "温度单位：celsius 或 fahrenheit"}
#   },
#   "required": ["location"]
# }

# ========== 使用示例（兼容 OpenAI tool format）==========
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": WeatherParams.__doc__,
            "parameters": WeatherParams.model_json_schema()
        }
    }
]

# ========== 多个工具组合 ==========
class SearchParams(BaseModel):
    """搜索知识库，支持关键词和过滤条件"""
    query: str = Field(description="搜索关键词")
    top_k: int = Field(default=5, description="返回结果数量")

# 用 Pydantic 统一管理所有 tools 定义，保持类型安全
ALL_TOOLS = {
    "get_weather": WeatherParams,
    "search_knowledge": SearchParams,
}

# 当 LLM 返回 tool_calls 时：
# tool_call.function.name -> 用 ALL_TOOLS[name] 查找模型
# json.loads(tool_call.function.arguments) -> 用 model_validate 校验参数
# params = WeatherParams.model_validate(json.loads(arguments))
# -> params.location, params.unit 类型安全
```

---

## 七、常见陷阱与最佳实践

| 陷阱 | 说明 | 对策 |
|------|------|------|
| 隐式类型转换 | `int` 字段传入 `"123"` 默认不会报错，宽松模式下自动转换 | 不需严格校验时无问题；需严格时设置 `model_config = ConfigDict(strict=True)` |
| 大模型返回非法 JSON | LLM 输出格式不稳定，可能缺少字段或类型不符 | 配合 PydanticOutputParser 做二次验证，catch `OutputParserException` |
| 循环引用 | 互相引用的模型（如 Employee.department 和 Department.employees） | 用 `ForwardRef` 注解字符串，最后调用 `model_rebuild()` |
| 性能敏感 | 高频场景下反复校验大量数据 | 用 `TypeAdapter` 替代 BaseModel 封装，或关闭不需要的校验 |
| 必填字段遗漏 | 开发时忘记给某个字段赋值 | 设置 `model_config = ConfigDict(validate_default=True)` 让默认值也过校验 |
| 可变默认值 | `items: List[str] = []` 不同实例共享同一个列表 | Pydantic 会自动深拷贝，V2 中无此问题。V1 需用 `default_factory=list` |
| 字段别名混淆 | 定义了 alias 但忘了设置 `populate_by_name=True` | 统一约定：API 层用别名，内部用原名。`ConfigDict(populate_by_name=True)` |

---

## 八、版本迁移要点（V1 -> V2）

| V1 API | V2 API | 说明 |
|--------|--------|------|
| `.dict()` | `.model_dump()` | 名称更明确 |
| `.json()` | `.model_dump_json()` | 同上 |
| `.schema()` | `.model_json_schema()` | 明确输出的是 JSON Schema |
| `@validator` | `@field_validator` | V1 的 @validator 行为复杂；V2 拆解为单字段/跨字段两个装饰器 |
| `@root_validator` | `@model_validator` | `mode="before"` 对应 V1 的 `pre=True`；`mode="after"` 是 V1 默认 |
| `Config` 内部类 | `model_config = ConfigDict(...)` | 从类内定义改为类属性赋值 |
| `__fields__` | `model_fields` | 运行时获取字段信息的 API 改名 |
| `construct()` | `model_construct()` | 跳过校验直接构建，用于性能敏感场景 |

> 迁移工具：`pip install bump-pydantic && bump-pydantic <files>` 可自动完成大部分迁移工作。
> 新项目直接使用 Pydantic V2，无需考虑向后兼容。
