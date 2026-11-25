# Third party components and data

Application source in this delivery is provided under AGPL-3.0-or-later; see `LICENSE`. No rights to user-provided invoices are granted by the source license.

| Component | Version used | License / source |
| --- | --- | --- |
| PyMuPDF | 1.26.6 | AGPL-3.0 / Artifex commercial alternative, https://pymupdf.readthedocs.io/ |
| RapidOCR ONNX Runtime | 1.4.4 | Apache-2.0, https://github.com/RapidAI/RapidOCR/tree/v1.4.4 |
| Bundled PP-OCRv4 det/rec and v2 classifier | From RapidOCR 1.4.4 wheel | PaddleOCR-derived models; Apache-2.0, https://github.com/PaddlePaddle/PaddleOCR |
| ONNX Runtime | 1.32.0 | MIT, https://github.com/microsoft/onnxruntime |
| FastAPI | 0.141.1 | MIT, https://github.com/fastapi/fastapi |
| React | 19.1.0 | MIT, https://github.com/facebook/react |
| TypeScript | 5.8.3 | Apache-2.0, https://github.com/microsoft/TypeScript |
| Vite | 6.4.6 | MIT, https://github.com/vitejs/vite |
| Recharts | 2.15.4 | MIT, https://github.com/recharts/recharts |
| Lucide React | 0.468.0 | ISC, https://github.com/lucide-icons/lucide |
| ReportLab | 4.4.9 | BSD, https://www.reportlab.com/ |
| OpenPyXL | 3.1.5 | MIT, https://openpyxl.readthedocs.io/ |

`models/APACHE-2.0.txt` retains the RapidOCR source license. `models/manifest.json` records exact bundled model filenames, sizes and SHA-256 hashes. Other Python / Node dependencies retain their own package licenses upon installation; `requirements.lock.txt` and `frontend/package-lock.json` record their versions.

The 23 original PDFs in `data/provided` were supplied by the user for this project. They are included only in this private delivery. They are not public training data, and the application license does not authorize their republication. No private invoices were uploaded to a third-party OCR service.

The documents in `data/demo` were generated specifically for this project. Their printed text identifies them as fictional teaching examples, not real transaction documents. Test rasterizations made from the provided PDFs are derivatives of the same source documents and do not increase the count of independently sourced invoices.

## 指定算法与数据

CTPN 原始权重来自 eragonruan/text-detection-ctpn，经 Open Model Zoo 镜像获取。CTPN 后处理适配自 Open Model Zoo，Apache-2.0 文本和来源保留在 models/classic/licenses。CRNN 初始化权重来自 Sierkinhane/CRNN_Chinese_Characters_Rec 固定提交 a565687c4076b729d4059593b7570dd388055af4；上游未明确声明权重许可证，不将应用代码的许可扩展到这些模型。VATID 来自 FuxiJia/InvoiceDatasets 固定提交 e0c2ab03a253552133f1a771b9a77eb20db20865，原图不随公开项目再次分发，许可边界需与源作者核实。未选用研究候选模型不在交付中。
