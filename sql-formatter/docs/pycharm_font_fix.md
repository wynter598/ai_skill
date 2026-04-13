# PyCharm 中文对齐字体配置指南

## 问题现象
SQL代码中包含中文字符的行，AS关键字在PyCharm中显示不对齐，但在终端中对齐正常。

## 根本原因
PyCharm使用的字体对CJK（中日韩）字符宽度处理不正确，导致视觉对齐偏差。

## 解决方案

### 方案1：更换支持CJK等宽的字体（推荐）

1. 打开 PyCharm → `Preferences/Settings` → `Editor` → `Font`
2. 更换为以下支持CJK等宽的字体之一：
   - **JetBrains Mono**（推荐，JetBrains官方字体）
   - **Consolas**（Windows系统自带）
   - **Source Code Pro**
   - **Fira Code**
3. 确保勾选 `Use different font for CJK characters`（如果有此选项）
4. 设置 Fallback font 为支持中文的等宽字体

### 方案2：使用等宽字体的中文补丁

下载并安装支持CJK的Nerd Font：
- https://www.nerdfonts.com/
- 推荐：JetBrains Mono Nerd Font

### 方案3：调整PyCharm渲染设置

1. `Help` → `Edit Custom VM Options`
2. 添加以下行：
   ```
   -Dide.text.width.calculation=accurate
   ```
3. 重启PyCharm

### 验证方法

在PyCharm中打开任意包含中文的SQL文件，检查以下字符是否等宽：
```
abc 123 +-= ()[]{}
中文汉字标点，。：；
```

如果中文字符看起来约等于两个英文字符宽度，说明配置正确。

## 如果以上方案都不生效

说明PyCharm的字体引擎对您当前系统的CJK字符宽度计算有限制。
此时可以考虑：
1. 使用外部编辑器（如VS Code）查看SQL文件
2. 使用终端编辑器（如vim/neovim）
3. 在代码审查时使用命令行工具验证对齐
