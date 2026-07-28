# 自动排版系统

AutoCAD插件，实现电脑针车模具的自动排版功能。

## 功能特点

- 在AutoCAD中框选图形，自动排版
- 支持8种板材规格（400x850, 600x850）
- 可设置图形间距（默认10mm）
- 排版结果写回原文件新图层
- 可视化预览排版结果

## 安装步骤

### 1. 安装Python依赖

```bash
pip install -r requirements.txt
```

### 2. 测试AutoCAD连接

```bash
python test_autocad.py
```

确保AutoCAD已运行，并且能成功连接。

### 3. 运行主程序

```bash
python main.py
```

## 使用流程

1. 启动AutoCAD 2007，打开要排版的文档
2. 运行 `python main.py` 启动排版工具
3. 点击"连接AutoCAD"
4. 在AutoCAD中框选要排版的图形
5. 选择板材尺寸，设置间距
6. 点击"执行排版"
7. 预览排版结果
8. 点击"写入CAD"将结果写入AutoCAD

## 项目结构

```
自动排版/
├── main.py              # 主程序入口
├── config.py            # 配置文件
├── autocad_bridge.py    # AutoCAD接口封装
├── geometry_utils.py    # 几何工具函数
├── test_autocad.py      # AutoCAD连接测试
├── requirements.txt     # 依赖包
├── nesting/
│   ├── rect_nesting.py  # 矩形排样算法
│   └── ...
├── gui/
│   └── ...
└── utils/
    └── ...
```

## 板材规格

| 类型 | 尺寸 (mm) | 厚度 |
|------|-----------|------|
| 400宽 | 400 x 850 | 0.5, 1.0, 1.5 |
| 600宽 | 600 x 850 | 1.0, 1.5, 2.0, 3.0, 4.0 |

## 注意事项

- 需要先启动AutoCAD再运行排版工具
- 目前仅支持矩形排样，不规则图形排样待开发
- 排版结果会创建新图层"排版结果"

## 后续开发

- [ ] 支持不规则图形排样
- [ ] 支持批量处理
- [ ] 优化排样算法
- [ ] 导出DXF文件
