# 跨平台与浏览器验收操作

工作流 `.github/workflows/acceptance.yml` 包含 Windows/macOS/Linux 原生环境、真实 Chromium、Docker 三组作业。它们使用同一指定网络、模型哈希和合成 PNG。原生检查实际启动 HTTP 服务、上传识别、轮询、核对票号日期金额并下载 XLSX；浏览器检查桌面七页、手机布局、文件选择、指定 OCR、修订持久化和真实下载，保存截图与失败 trace。

**这些远程 CI 作业尚未执行。** 当前环境没有 GitHub 写入凭据；公开仓库可读取不等于允许提交或启动工作流。但本机已直接用 Playwright Chromium 完成真实浏览器界面验收（桌面 + 移动端，13 张截图），并在 Windows 11 上完成原生验收，证据见 [验收执行记录](11-acceptance-execution.md)。macOS 运行器与 Docker 守护进程仍不可用，因此这两类以及 CI 远程作业不能把配置或测试用例列为已通过。

## 仓库授权后

将已准备的 `delivery/required-networks` 分支推送到 `qjl-411/OCR` 即触发工作流。需要对该仓库有写入源码和工作流的授权。然后在仓库 Actions 页面等待所有作业完成，下载 native、docker 和 real-browser-evidence 产物；审阅真实截图与日志，修复失败后重跑相关部分。

仅成功的实际作业和产物可写入最终验收表。Windows 与 Mac 的实际版本、CPU 架构、Python 版本由 smoke JSON 记录；库存在安装包不代表对应系统实测。

## 使用离线 Git bundle 的备选步骤

在已登录 GitHub 的本机新目录执行，将 BUNDLE_PATH 替换为下载的 bundle 的实际绝对路径：

```bash
git clone https://github.com/qjl-411/OCR.git piao-ocr-review
cd piao-ocr-review
git fetch BUNDLE_PATH refs/heads/delivery/required-networks
git switch -c delivery/required-networks FETCH_HEAD
git push -u origin delivery/required-networks
```

这会保留原始 main，提交新分支。公开分发包不含原始发票、私有回归参考、训练裁剪或本地数据库。模型权重的来源与授权边界保留在说明中。

## 本地复核

Windows：安装 Python 3.12 后运行 start.bat；macOS：运行 `sh start.sh`；Docker：`docker compose up --build -d`。验证上传、强制图像 PDF、识别框、修改后复核、重复限制、导出、刷新和重启后的持久化，核对桌面与窄屏文字溢出。真实界面截图只能证明相应界面状态，不能替代 OCR 准确率或跨系统运行结果。
