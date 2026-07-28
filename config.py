"""
自动排版系统 - 配置文件
"""

# AutoCAD配置
AUTOCAD_VERSION = "2007"  # AutoCAD版本
AUTOCAD_PROGID = "AutoCAD.Application"  # COM ProgID

# 板材规格 (宽度x高度, 单位: mm)
BOARD_SIZES = {
    "400x850-0.5": (400, 850, 0.5),
    "400x850-1.0": (400, 850, 1.0),
    "400x850-1.5": (400, 850, 1.5),
    "600x850-1.0": (600, 850, 1.0),
    "600x850-1.5": (600, 850, 1.5),
    "600x850-2.0": (600, 850, 2.0),
    "600x850-3.0": (600, 850, 3.0),
    "600x850-4.0": (600, 850, 4.0),
}

# 默认板材尺寸
DEFAULT_BOARD = "400x850-1.0"

# 排版参数
NESTING_SPACING = 10.0  # 图形间距 (mm)
NESTING_MARGIN = 10.0   # 边缘留白 (mm)

# 遗传算法参数 (用于不规则图形排样)
GA_POPULATION_SIZE = 50
GA_GENERATIONS = 100
GA_MUTATION_RATE = 0.1

# GUI配置
WINDOW_TITLE = "自动排版工具"
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600

# 图层配置
LAYER_NAME = "排版结果"
LAYER_COLOR = 1  # 红色 (AutoCAD颜色索引)
