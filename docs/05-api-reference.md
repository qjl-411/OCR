# 接口说明

根地址为 `http://127.0.0.1:8000`。主界面和 API 使用相同域名，无需配置 API 密钥。JSON 金额字段为两位小数字符串或 `null`；票号、代码与税号都是字符串。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /api/health | 版本和 OCR 可用状态 |
| GET | /api/meta | 设置、分类、数据集数量和上传限制 |
| GET | /api/dashboard | 按日期与来源汇总统计 |
| GET | /api/invoices | 筛选、排序、分页的票据列表 |
| GET | /api/invoices/{id} | 完整字段、文字框、原文与异常 |
| GET | /api/invoices/{id}/preview | 提供票据预览图 |
| GET | /api/invoices/{id}/original | 提供原始上传文件 |
| PATCH | /api/invoices/{id} | 保存人工修订并退回待复核 |
| POST | /api/invoices/{id}/review | 确认、驳回或退回复核 |
| DELETE | /api/invoices/{id} | 删除记录及无引用原件，保留审计 |
| POST | /api/imports | multipart 多文件上传，返回后台任务 |
| POST | /api/datasets/{source}/import | 导入 provided 或 demo 目录 |
| GET | /api/datasets/demo/sample | 下载有明确演示标记的 PNG |
| GET | /api/jobs | 最近 30 个任务 |
| GET | /api/jobs/{id} | 单个任务实时进度和逐文件结果 |
| GET | /api/export | 导出 xlsx、csv 或 json |
| GET | /api/audit | 操作日志，支持动作筛选和分页 |
| PATCH | /api/settings | 更新工作区与复核规则 |
| GET | /openapi.json | 机器可读 OpenAPI |
| GET | /docs | 本地接口文档，无外部脚本依赖 |

## 查询参数

`/api/invoices` 支持 `q`、`status`、`category`、`source`、`start`、`end`、`sort`、`page` 和 `page_size`。日期为 `YYYY-MM-DD`；每页默认 10 条，最大 100 条。排序包括 `newest`、`date_desc`、`amount_desc`。状态可用 `needs_review`、`approved`、`rejected`，以及异常集合 `anomaly` 和重复集合 `duplicate`。来源为 `provided`、`upload`、`demo`；空值表示不限。

`/api/dashboard` 支持 `start`、`end`、`source`。金额统计只包含已确认且非重复的票据。

`/api/export` 支持相同的查询条件、`ids`（逗号分隔）和 `format`（xlsx / csv / json）。`ids` 与筛选条件取交集，空结果返回 422。

## 上传与轮询

```bash
curl -F "pipeline=classic" -F "force_ocr=true" -F "files=@example.pdf" http://127.0.0.1:8000/api/imports
curl http://127.0.0.1:8000/api/jobs/返回的任务id
```

上传接口接受 multipart 表单，字段名重复使用 `files`，返回 HTTP 202 和任务对象。接受上传不代表识别完成；应轮询任务的 `status`。文件级识别错误保存在 `results`，导入前的格式或 ZIP 条目问题保存在 `errors`。`total` 与 `processed` 按文件统计，PDF 的每页可能生成单独票据。

## 人工修改与确认

修改接口要求提交全部可编辑字段和当前 `revision`。保存成功后返回更新后的票据与新版本。确认请求示例：

```json
{"revision": 2, "verdict": "approved", "note": ""}
```

`verdict` 可为 `approved`、`rejected` 或 `needs_review`。驳回需要非空原因。存在必填缺失、金额不平或重复时，确认返回 422。版本冲突返回 409，调用者应重新读取，不能静默覆盖。

## 常见返回状态

| 状态码 | 含义 |
| --- | --- |
| 200 | 查询或操作成功 |
| 202 | 上传已接受，任务进入队列 |
| 403 | 跨站写入被拒绝 |
| 404 | 记录、文件或接口不存在 |
| 409 | 数据版本过期 |
| 413 | 批次或上传数量超出限制 |
| 422 | 参数、空导出、复核条件等检查失败 |
| 503 | 缺少前端构建文件 |

## 指定识别模式

上传表单接受 `force_ocr=true|false`，默认 false：电子 PDF 读取内嵌文字，扫描件可强制走图像识别。
数据集导入接受相同查询参数。

`pipeline=classic|ppocr` 为可选参数，默认 classic。**界面不提供引擎选择入口**，客户端不传即使用指定的
CTPN / CRNN / CTC；显式传入 `ppocr` 仅用于对照测试。engine 分别为 pdf_text、ctpn_crnn_ctc、ppocr。
processing_profile 保留配置、模型版本、原件哈希和耗时。指定网络失败直接报错，不回退其他模型。

`GET /api/meta` 的 `pipelines` 字段同时给出默认引擎与两条通道的可用状态，供诊断与验收核对。
