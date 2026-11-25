# 验收执行记录（2026-11-21 起，持续更新）

本文件记录**实际执行**的验收，不把配置或用例的存在写成通过。此前 README 与
`docs/10-cross-platform-acceptance.md` 所述的"远程作业尚未执行"在本次执行前成立；
本次在本机补充了 Windows 原生与真实浏览器的实测，Docker 与 macOS 仍未执行。

## 2026-11-22 交付级界面改版后的复验

界面改版（登录注册、去重、视觉升级）完成后重新执行了本机验证：

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 前端单测 | 8 通过 / 0 失败（原 5 项 + 新增 3 项登录注册） | `npm --prefix frontend test` |
| 后端单测 | 37 通过 / 0 失败（界面改版未影响业务逻辑） | `pytest -q` |
| TypeScript + Vite 构建 | 通过 | `npm run build`，dist 三资源已更新 |
| 真实浏览器 · 桌面 | 通过（24.9s）：登录 → 六页导航 → 真实 OCR → 复核 → XLSX 下载 → 刷新持久化 | `docs/acceptance-evidence/ui-redesign/e2e.log` |
| 真实浏览器 · 移动端 | 通过（3.9s）：导航、控件与文档无横向溢出 | 同上 |
| 界面截图 | 7 张（登录、注册、工作台、分析报告、台账、设置、移动端） | `docs/acceptance-evidence/ui-redesign/*.png` |

### 本轮修复的缺陷

1. **密码强度指示条越界崩溃**：空密码时 `STRENGTH[strength-1]` 访问 `undefined.color`，
   注册页在清空密码即抛错。改为 `STRENGTH[Math.max(0, strength-1)]`。
2. **移动端布局塌缩**：`theme.css` 的 `@media(max-width:1250px)` 规则晚于
   `styles.css` 的 760px 规则加载，覆盖了 `.main-shell{margin-left:0}`，
   390px 下主内容仅 178px 宽、文字竖排。已在 760px 断点显式归零偏移。
3. **移动端横向溢出**：费用构成图例超出视口 16px。改为窄屏单列自适应，
   几何探针复测 `scrollWidth === innerWidth`。
4. **E2E 选择器失效**：侧栏「发票台账」因带待复核数量徽标，`exact:true` 无法匹配，
   改为正则前缀匹配。

## 执行环境

| 项 | 实测值 | 来源 |
| --- | --- | --- |
| 操作系统 | Windows 11（10.0.26300）AMD64 | `docs/windows-native-results.json` platform/machine |
| Python | 3.12.14（uv 管理的 CPython） | `python --version`、smoke JSON |
| Node / npm | 22.22.2 / 10.9.7 | `node --version`、`npm --version` |
| Playwright Chromium | 141.0.7390.37，build 1194 | `npx playwright install chromium` 输出 |
| 依赖完整性 | `No broken requirements found.` | `.venv/Scripts/python.exe -m pip check` |
| Docker | 不可用（`docker: command not found`） | 本机命令探测 |
| macOS | 无对应系统 | 本机为 Windows |

## 已通过

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| Python 依赖安装 + pip check | 通过 | 本次执行，`pip check` 输出见上 |
| 后端单测 | 37 通过 / 0 失败 | `test-results/windows-backend.xml`：`tests="37" errors="0" failures="0"`，hostname `LAPTOP-76AI78RB` |
| 前端单测 | 5 通过 / 0 失败 | 本次 `npm test` 输出：Test Files 1 passed、Tests 5 passed |
| TypeScript + Vite 构建 | 通过 | 本次 `npm run build`：2002 modules transformed，dist 三个资源已更新 |
| 真实 HTTP + 指定图像 OCR + XLSX 下载 | 通过 | `docs/windows-native-results.json`：engine `ctpn_crnn_ctc`，票号/日期/三项金额全部命中，`xlsx_download: passed` |
| 模型 SHA-256 校验 | 通过 | 同上 `model_hashes: passed`；`scripts/restore_models.py` 输出 "restored and verified" |
| 真实浏览器 · 桌面七页 + 指定 OCR + 复核 + 下载 + 刷新持久化 | 通过 | `e2e-decisive.log`：`ok 1 ... (21.7s)`；截图 `frontend/test-results/acceptance-desktop-seven-p-79b4a-ew-download-and-persistence/`（7 页 + review） |
| 真实浏览器 · 移动端导航与文档溢出 | 通过 | `e2e-decisive.log`：`ok 2 ... (2.9s)`；截图 `frontend/test-results/acceptance-mobile-navigation-controls-and-document-overflow/`（5 页） |

桌面用例的关键断言在真实 Chromium 中均成立：七页导航无横向溢出、`demo-12.png`
经 CTPN→CRNN→CTC 识别、票号 `99000000000000000012` 与价税合计 `186.00`、
识别框叠加与字段高亮、人工修订后"等待人工确认"、刷新后备注持久化、XLSX 下载。
复核工作区截图中可见 "CTPN → CRNN → CTC · 平均分 97%（非准确率）" 的标注。

## 本次发现并修复的缺陷

1. **测试代码跨平台缺陷（已修复）**：`tests/test_parser.py::test_masked_tax_remains_unknown`
   原用 `next(glob('DZFP_*.pdf'))` 选取被遮盖税额样本。Windows 文件系统大小写不敏感，
   glob 匹配到小写 `dzfp_*.pdf`（其税额 0.39 明印在合计行），导致断言失败；Linux 上
   只匹配大写样本，故此前 37/37 通过。经核验产品代码行为正确：显式读取
   `DZFP_26367000000002725372.pdf` 得到 `tax_amount: None`。
   修复为按精确文件名锁定样本，不依赖 glob 顺序与大小写。修复后本机 37/37 通过。
2. **E2E 运行注意事项（非产品缺陷）**：桌面用例的"保存修改"按钮在字段值已被前一次
   运行写入时会因 `dirty=false` 而禁用，导致重复运行同一数据目录超时。E2E 应使用
   全新 `INVOICE_DATA_DIR`；本次最终证据来自全新目录 `.qa/e2e-final-1795269911`。

## 仍未执行（NOT_EXECUTED）

| 项 | 原因 | 后续步骤 |
| --- | --- | --- |
| macOS 原生 | 本机无 macOS | 需 macOS 运行器执行 `acceptance.yml` 的 native(macos-latest) |
| Docker 容器 | 本机无 Docker CLI/守护进程 | 需有 Docker 的环境执行 `docker build` + `docker run` + `verify_delivery.py --base-url` |
| GitHub Actions 三组远程作业 | 无仓库写入凭据 | 授权后将 `delivery/required-networks` 分支推送至 `qjl-411/OCR` 触发，详见 `docs/10` |

## 证据文件清单

持久证据（不受 .gitignore 影响）：

- `docs/windows-native-results.json` — Windows 真实 HTTP 冒烟结果
- `docs/acceptance-evidence/windows-backend.xml` — 37 项后端测试 JUnit 报告
- `docs/acceptance-evidence/e2e-decisive.log` — 两个真实浏览器用例的通过记录
- `docs/acceptance-evidence/desktop-工作台.png`、`desktop-review.png`、`mobile-工作台.png` — 关键界面截图

临时产物（在 .gitignore 中，仅本机留存）：`test-results/`、
`frontend/test-results/**/*.png`（13 张完整截图）、`.qa/`（各次验收的数据目录）。

说明：本机 Playwright 在测试通过后关闭 webServer 较慢，命令行进程需手动终止；
`e2e-decisive.log` 的两个 `ok` 行与截图是测试通过的直接证据。
