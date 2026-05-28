# 杨轩的博客

在线访问：https://codedatayx.github.io/my-blog/

管理后台：https://codedatayx.github.io/my-blog/admin/

## 技术栈

- **前端**: Hugo + PaperMod 主题
- **管理后台**: Decap CMS（Git-based）
- **AI 聊天**: FastAPI + DeepSeek（数字分身）
- **部署**: GitHub Pages + GitHub Actions

## 功能

- 文章发布与管理
- 暗黑/亮色模式自动切换
- 全文搜索（Fuse.js）
- 代码语法高亮 + 复制按钮
- RSS 订阅
- 标签/分类/归档
- AI 数字分身聊天
- SEO 优化

## 本地开发

```bash
# 安装 Hugo
snap install hugo

# 启动开发服务器
hugo server -D

# 访问 http://localhost:1313/my-blog/
```

## 启动 AI 聊天后端

```bash
cd backend
docker compose up -d
```

## 部署

推送到 `main` 分支后，GitHub Actions 自动构建并部署到 GitHub Pages。
