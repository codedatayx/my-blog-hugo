---
title: "Python 实用技巧整理"
date: 2026-05-15
description: "收集了一些日常开发中常用的 Python 小技巧，包括列表操作、字典合并、类型提示等。"
author: "杨轩"
tags: ["Python", "编程技巧"]
categories: ["技术笔记"]
showtoc: true
ShowReadingTime: true
ShowCodeCopyButtons: true
---

日常写 Python 积累了不少小技巧，这里做一次集中整理。

## 1. 列表去重保序

```python
nums = [3, 1, 2, 1, 3]
unique = list(dict.fromkeys(nums))  # [3, 1, 2]
```

用 `dict.fromkeys` 既去重又保持原始顺序，比 `set()` 好用。

## 2. 字典合并

```python
a = {'x': 1}
b = {'y': 2}
merged = a | b  # Python 3.9+，简洁优雅
```

## 3. 海象运算符

在 while 循环和列表推导中特别好用：

```python
while chunk := f.read(8192):
    process(chunk)
```

这些小技巧虽然不起眼，但积少成多，能让代码更 Pythonic。
