# 第 0 课：给 Java 程序员的 Python 速成（30 分钟）

只讲这门课要用到的，不求全。你是老程序员，对照着看就懂。

## 1. 核心差异一句话

Python = 不用声明类型、不用分号、**用缩进代替大括号**、解释执行。

```python
# Java: String name = "小明";
name = "小明"          # 变量直接赋值，类型自动推断

# Java: if (age > 18) { ... }
age = 20
if age > 18:           # 冒号开头，下面缩进 4 个空格
    print("成年了")     # print = System.out.println
```

⚠️ 缩进就是语法！同一代码块必须缩进一致，这是新手最容易踩的坑。

## 2. 最常用的四种数据结构

```python
# 列表 ≈ Java 的 ArrayList
fruits = ["苹果", "香蕉"]
fruits.append("橙子")
print(fruits[0])        # 苹果

# 字典 ≈ Java 的 HashMap<String, Object>（JSON 就长这样）
user = {"name": "小明", "age": 20}
print(user["name"])     # 小明

# 元组：不可变列表，先混个脸熟
point = (1, 2)

# f-string ≈ Java 的 String.format，最常用！
print(f"我叫{user['name']}，今年{user['age']}岁")
```

## 3. 函数与 import

```python
# Java: public static int add(int a, int b) { return a + b; }
def add(a, b):
    return a + b

# import ≈ Java 的 import，但可以起别名
import os
from dotenv import load_dotenv   # 从包里只导入某个东西
```

## 4. 虚拟环境 venv ≈ 每个项目独立的 Maven 仓库

不同项目依赖版本会打架，所以每个项目一个隔离环境：

```powershell
python -m venv .venv          # 创建（只需一次）
.venv\Scripts\Activate.ps1    # 激活（每次开新终端都要）
pip install -r requirements.txt  # 装依赖 ≈ mvn install
```

激活后命令行前面会出现 `(.venv)` 标记。

## 5. 一个完整小例子（看懂它就够开始第 1 课了）

```python
import os                       # 操作系统接口，读环境变量用

def greet(name, times=1):       # times=1 是默认参数
    for i in range(times):      # range(3) = 0,1,2
        print(f"[{i+1}] 你好，{name}！")

if __name__ == "__main__":      # 程序的 main 入口约定
    greet("小明", times=2)
```

## 6. 异常处理

```python
try:
    result = 1 / 0
except ZeroDivisionError as e:   # ≈ catch (Exception e)
    print(f"出错了：{e}")
```

---

✅ **过关自测**：不看上面，默写——定义一个函数接收一个字典，用 f-string 打印里面两个字段。能写出来就进第 1 课。
