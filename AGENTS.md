# AGENTS.md — CRO仪器排程系统

## 技术栈
- 后端: Python 3.12 + FastAPI + SQLAlchemy + MySQL/SQLite
- 前端: React 18 + TypeScript + Ant Design 5 + Recharts + vis-timeline
- 排程引擎: OR-Tools CP-SAT（Phase 2 引入）

---

## 后端规则

### 分层架构
```
api/        → 路由层：解析请求、调用一个 service、返回响应
services/   → 业务层：编排逻辑，不 import FastAPI/HTTPException
models/     → 数据层：SQLAlchemy ORM 模型
schemas/    → 接口层：Pydantic 请求/响应模型
core/       → 配置层：config + database 连接
```

### 路由层 (api/)
- 每个 handler ≤ 15 行
- 只做三件事：解析输入 → 调用 service → 返回响应
- 不在路由里写 SQL 或业务逻辑
- 每个端点声明 `response_model=`

### 业务层 (services/)
- 不 import `fastapi.HTTPException`
- 不 import `sqlalchemy`（那是 models 的事）
- 抛业务异常，由路由层转 HTTP 状态码

### 文件大小
- 单文件超过 400 行 → 计划拆分
- 单文件超过 600 行 → 必须先拆分再继续

---

## 前端规则

### 组件
- 用函数组件，不用 class
- 状态尽量靠近使用处，不提前提升
- 提取重复逻辑到自定义 hook

### TypeScript
- 对象定义用 `interface`，联合类型用 `type`
- 禁止 `any`，用 `unknown` 或具体类型
- Props 接口以 `Props` 结尾（如 `GanttProps`）
- `tsconfig.json` 保持 `strict: true`

### 命名
- 组件文件: PascalCase（`InstrumentGantt.tsx`）
- 工具/hook 文件: camelCase（`useSchedule.ts`）
- 变量/函数: camelCase，布尔值加 `is/has` 前缀

### 状态管理
- 单页面状态用 `useState`
- 跨组件共享用 React Context（不引入 Redux）
- API 请求结果直接存在调用组件中

---

## 通用规则

### 反过度设计
- 只改用户要求的部分，不改无关代码
- 先上最简单的方案，确实需要再抽象
- 不为"以后可能"的需求写代码

### 代码质量
- 魔法数字用命名常量替代
- 函数只做一件事
- 重复代码提取为公共函数
- 变量名自解释，不加废话注释

### 提交
- 小步提交，一个改动一个 commit
- commit message 用中文描述做了什么
