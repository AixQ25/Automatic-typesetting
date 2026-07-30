# 自动排版系统

DXF文件自动排版工具，实现电脑针车模具的自动排版功能。

## 功能特点

- 导入DXF文件，自动识别零件并按厚度分组排版
- 统一使用600×850板材，自动计算每种厚度需要几张
- 容器/参考框自动剥离，防止吞并零件
- 保留原始图层和颜色（底板/面板/卡板等）
- 板子横向排列（一行满自动换行）
- 列优先排布（纵向填满列再开新列）
- 小圆等内部图元完整保留不丢失

## 安装步骤

```bash
pip install -r requirements.txt
```

## 使用流程

```bash
python main.py
```

1. 点击"导入DXF"选择文件
2. 设置间距（默认10mm）
3. 点击"执行排版"
4. 预览排版结果
5. 点击"导出DXF"保存结果

无GUI回归诊断：
```bash
python tools/diagnose.py test_pro(1).dxf
```

## 项目结构

```
自动排版/
├── main.py                          # 主程序 + GUI
├── config.py                        # 配置（板材规格、间距）
├── geometry_utils.py                # 几何工具
├── requirements.txt                 # 依赖包
├── utils/
│   ├── dxf_parser.py                # DXF解析（INSERT变换）
│   ├── dxf_writer.py                # DXF写入（横向排列、原层保留、EXT修复）
│   ├── text_parser.py               # 文字标注解析（厚度/跳过/W×H×T）
│   ├── shape_grouper.py             # 厚度分组（每件按最近标注归属）
│   └── containment_detector.py      # 包含关系检测（容器剥离+整体识别）
├── nesting/
│   ├── rect_nesting.py              # 列优先矩形排样
│   └── board_optimizer.py           # 多板材装箱（统一600×850）
├── tools/
│   └── diagnose.py                  # 无GUI回归诊断
└── gui/
    └── __init__.py
```

## 板材规格

| 尺寸 (mm) | 说明 |
|-----------|------|
| 600 x 850 | 统一使用（边距10mm，间距10mm） |

## 注意事项

- 输入文件中的厚度标注格式：纯数字（1.0/1.5/2.0）或 W×H×T（600×850×1.0）
- 多数字空格串（如"4.5 5 6 7 8"）为尺寸规格，自动忽略
- "暂不"、"no" 标注的部件组会被跳过
- 超大零件（>580×830）自动略过不排
- 输出文件中零件保留原图层颜色，板材边框在厚度图层
