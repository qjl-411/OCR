# 票序 智能财务发票系统 v2.0

指定算法验收候选版：React + TypeScript 前端、FastAPI 后端、本地 SQLite。图片和扫描 PDF 实际使用 **CTPN → CRNN → CTC**，有文字层的电子 PDF 可直接解析。提供登录注册、批量识别、人工复核、重复校验、费用分类、分析报告、审计日志和 Excel / CSV / JSON 导出。

**本地算法与业务验证、Windows 原生验收、真实 Chromium 桌面与移动端 E2E 已在本机实际执行并通过；macOS 与 Docker 仍待有对应环境的运行器执行，当前不称为全部平台验收完成。** 具体数据见 [验收报告](docs/06-validation-report.md) 与 [验收执行记录](docs/11-acceptance-execution.md)。PP-OCR 仅保留为需要明确选择的旧版对比通道，指定网络失败时直接报错，不回退。

## 运行

安装 64 位 Python 3.12，进入解压后的项目目录：

```bash
python start.py
```

Windows 可双击 `start.bat`，macOS / Linux 可运行 `sh start.sh`。首次安装依赖需联网；模型和依赖齐全后在本机处理发票，不调用云端 OCR。运行预构建界面不需要 Node.js。默认打开 `http://127.0.0.1:8000`，按 Ctrl+C 停止。

```bash
python start.py --port 8010 --no-browser
python start.py --no-demo
python start.py --install-only
```

建议 4 核 CPU、8 GB 内存、2 GB 可用磁盘；GPU 不是运行和本次微调的必要条件。macOS 运行库要求 13 或以上。数据保存在 `runtime`，也可用 `INVOICE_DATA_DIR` 指定位置。Git 源码中的模型分卷由启动器自动校验并重组；离线交付包直接附完整 ONNX 文件。

启用登录注册时，把项目根目录 `.env.example` 复制为 `.env`，填入 MySQL 密码、JWT 密钥与 SMTP 邮箱授权码；启动器会自动加载。

## 使用闭环

1. 首次打开进入登录页。注册需填写姓名、公司、邮箱、密码，并**通过邮箱收到的 6 位验证码**完成验证；验证码 10 分钟有效、仅可使用一次。账号保存在 MySQL `piao_invoice`，口令以 bcrypt 哈希存储。登录状态用 JWT 令牌维持，可随时退出。
2. 在识别中心上传 PDF / PNG / JPG / ZIP。电子 PDF 默认读取文字层，扫描件可勾选“按图片识别”。
3. 在发票台账的「待复核」标签对照原图、识别框和提取字段，修订错误，确认或填写原因驳回。
4. 必填字段、金额关系和重复检查通过后才能确认；统计仅计入已确认的非重复票据。
5. 在分析报告查看供应商排行、费用结构、月度明细与票据构成；台账可按日期、分类、状态和来源筛选，导出 Excel、CSV 或 JSON；操作记录保存变更历史。

票号和税号保留为字符串，金额使用 Decimal，未知税额保持 null。规则检查不提供税务真伪查验。模型分数不是准确率，所有新上传记录都进入人工复核。

账号与邮件服务的配置见 [账号与邮箱验证](docs/08-authentication.md)。

## 数据与模型

私人交付包包含原始 23 张 PDF；公开 Git 源码排除原始发票、私人参考值、裁剪图和本地数据库。11 张初始 PDF 与额外 1 张 PNG 都明确标注为虚构教学示例。

CTPN 使用原始 VGG16 / 双向 LSTM 预训练网络并进行数值校验；CRNN 使用 7 个卷积层和两层双向 LSTM，实际微调两阶段共 1200 步；训练为 CTCLoss，推理显式 CTC 解码。权重、来源、SHA-256 和逐步 loss 均随包提供，详见 [数据与模型](docs/04-data-and-models.md) 和 [训练复现](docs/09-training-and-reproduction.md)。

独立评估严格按票据身份排除训练和历史开发数据：VATID 0030、0035 是同一张未见发票的两张照片；另有两份此前未用的官方文档发票示例。样本非常小。0081–0100 存在票据身份重合，只保留为图片留出成绩。水平关键词端到端召回为 29/50；外部示例的六项字段合计命中 5/12，不能称为高精度整票识别。竖排标签未有效支持，所有新发票需要人工复核。

## 开发与验证

```bash
python start.py --install-only
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
npm --prefix frontend ci
npm --prefix frontend test
npm run build
.venv/bin/python scripts/verify_delivery.py
```

Windows 将 `.venv/bin/python` 替换为 `.venv\Scripts\python.exe`。独立评估命令：

```bash
.venv/bin/python scripts/fetch_evaluation_data.py
.venv/bin/python scripts/evaluate_classic.py --dataset evaluation/vatid-final
.venv/bin/python scripts/evaluate_external.py --download-only
.venv/bin/python scripts/evaluate_external.py
```

脚本只下载已固定来源的原图和人工标注，不调用云 OCR、PP-OCR 或 PDF 文字层。票据分组审查在 `data/vatid-identity-audit.json`；两个独立协议均在首次识别前写定。结果分别在 `docs/independent-classic-results.json` 和 `docs/external-classic-results.json`。

## Docker 与跨平台

```bash
docker compose up --build -d
docker compose logs -f
```

数据保存在命名卷；停止服务使用 `docker compose down`，需要保留数据时不要删除卷。提供配置不代表已执行容器验收。Windows/macOS/Linux、Docker 与真实 Chromium 的工作流见 `.github/workflows/acceptance.yml`，实际执行与授权说明见 [跨平台验收](docs/10-cross-platform-acceptance.md)。

[项目脉络](docs/01-project-plan.md) · [前端设计](docs/02-interface-design.md) · [架构](docs/03-architecture-and-development.md) · [接口](docs/05-api-reference.md) · [演示答辩](docs/07-demo-and-defense.md) · [验收执行记录](docs/11-acceptance-execution.md)
