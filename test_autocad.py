"""
AutoCAD连接测试脚本
运行此脚本测试pyautocad是否能连接到AutoCAD
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_pyautocad():
    """测试pyautocad库"""
    print("=" * 50)
    print("AutoCAD连接测试")
    print("=" * 50)
    
    # 1. 检查pyautocad是否安装
    print("\n1. 检查pyautocad库...")
    try:
        import pyautocad
        print(f"   pyautocad版本: {pyautocad.__version__ if hasattr(pyautocad, '__version__') else '未知'}")
        print("   ✓ pyautocad已安装")
    except ImportError:
        print("   ✗ pyautocad未安装")
        print("   请运行: pip install pyautocad")
        return False
    
    # 2. 检查comtypes
    print("\n2. 检查comtypes库...")
    try:
        import comtypes
        print(f"   comtypes版本: {comtypes.__version__}")
        print("   ✓ comtypes已安装")
    except ImportError:
        print("   ✗ comtypes未安装")
        print("   请运行: pip install comtypes")
        return False
    
    # 3. 尝试连接AutoCAD
    print("\n3. 尝试连接AutoCAD...")
    try:
        from pyautocad import Autocad
        acad = Autocad()
        print(f"   ✓ 已连接到AutoCAD")
        print(f"   文档名称: {acad.doc.Name}")
        
        # 4. 测试获取模型空间
        print("\n4. 测试获取模型空间...")
        model = acad.model
        print(f"   ✓ 模型空间获取成功")
        
        # 5. 测试添加简单图形
        print("\n5. 测试添加图形...")
        from pyautocad import APoint
        p1 = APoint(0, 0)
        p2 = APoint(100, 100)
        line = model.AddLine(p1, p2)
        print(f"   ✓ 成功添加一条测试线段")
        
        # 删除测试线段
        line.Delete()
        print(f"   ✓ 成功删除测试线段")
        
        print("\n" + "=" * 50)
        print("所有测试通过！AutoCAD连接正常")
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"   ✗ 连接失败: {e}")
        print("\n可能的原因:")
        print("1. AutoCAD未运行")
        print("2. AutoCAD版本不兼容")
        print("3. COM接口权限问题")
        return False


if __name__ == "__main__":
    test_pyautocad()
    input("\n按回车键退出...")
