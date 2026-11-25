# 训练与复现操作

本项目已经在 CPU 上完成两阶段 1200 步训练，无需你准备 GPU。当前机器实测分别约 80.2 秒与 154.6 秒；其他机器请先跑 100 步测速度再估算。建议 Python 3.12、4 核 CPU、8 GB RAM、5 GB 可用磁盘用于训练环境。下面命令以 Linux 为已验证环境；Windows 的解释器路径换为 `.venv\Scripts\python.exe`。

## 安装与源权重

```bash
python start.py --install-only
.venv/bin/python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.8.0+cpu
.venv/bin/python -m pip install -r requirements-training.txt
.venv/bin/python scripts/download_training_sources.py
```

下载脚本取得固定来源的 CTPN 冻结图和原 CRNN 检查点并校验 SHA-256。原 checkpoint 用 `weights_only=True` 加载。日常运行无需安装 PyTorch、OpenVINO 和 ONNX 转换库。

## 准备训练数据

将原始 23 张 PDF 放在 `data/provided`，安装 Noto Sans CJK 和 Noto Serif CJK 字体。当前脚本使用 Linux 字体路径，其他系统应指定对应字体路径再运行，并记录字体变动；没有相同附件和字体不能声称逐字节复现权重。

```bash
.venv/bin/python training/prepare_crnn_data.py
.venv/bin/python training/finetune_crnn.py --checkpoint training/source/crnn-source.pth --steps 400 --run-name required-crnn
.venv/bin/python training/prepare_camera_data.py
.venv/bin/python training/finetune_crnn.py --checkpoint training/runs/required-crnn/finetuned.pth --data training/camera-data --run-name camera-adaptation --steps 800
```

第一阶段标签来自 PDF 文字对象与明确合成字符串，第二阶段来自 VATID 官方训练集人工关键词标注，不使用 PP-OCR 标签，也不使用最终测试图片。所有步的 loss 和耗时逐行保存；元数据保存源检查点、数据清单和输出检查点哈希。

## 转换和数值核对

```bash
.venv/bin/python training/convert_ctpn.py --source training/source/ctpn.pb
.venv/bin/python training/export_crnn.py --checkpoint training/runs/camera-adaptation/finetuned.pth
.venv/bin/python scripts/update_model_manifest.py
.venv/bin/python scripts/checkpoint_model_parts.py
```

CTPN 以 OpenVINO 执行原始冻结图为参考，比较三个输入尺寸；CRNN 比较四个输入宽度，断言原始输出误差阈值，并检查 7 Conv / 2 BiLSTM。更新模型后必须更新 manifest 和模型分卷，并重新评估，不能继续使用旧权重的准确率。

## 独立评估

```bash
.venv/bin/python scripts/fetch_evaluation_data.py
.venv/bin/python scripts/evaluate_classic.py --dataset evaluation/vatid-final
.venv/bin/python scripts/evaluate_external.py --download-only
.venv/bin/python scripts/evaluate_external.py
```

原 0081–0100 有与训练集相同发票的不同照片，已经撤回“票据级独立”表述，保留原结果以便审计。按全部 100 张原图的印刷票号人工分组，保守排除训练、开发及全部历史评估 0001–0025、0051–0100 中的所有身份，余下 0030、0035，两张照片同属一张新票。公开分组和选择规则在 data/vatid-identity-audit.json，模型首次处理该子集前已经写定 data/evaluation-split.json。另两份外部官方文档示例的六项字段也在首次推理前人工抄录并固定。测试后未再修改网络权重、输入预处理和字段解析规则。

报告记录每个输入、模型和实现的哈希；关键词协议采用 NFKC 并对双方去除标注未包含的标点空格，分别报告水平与竖排。外部字段采用预声明字符串精确匹配，不人工订正输出。全部独立数据只有三张不同发票，数量不足以证明广泛泛化。

如果自行扩大实验而使用 NVIDIA GPU，需按 PyTorch 官方说明选择匹配驱动与 CUDA 构建，训练参数改为 `--device cuda`，先用 batch=8 检查显存，再测得速度。当前没有 GPU 实测时间，因此不提供未经测量的 GPU 耗时；当前交付推进也不以用户 GPU 为前提。
