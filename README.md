# Resume Document Webpage

一个可自行替换内容的个人主页与简历网页模板，包含四图自动轮播、研究方向卡片、桌面/手机适配，以及浏览器端 PDF 导出。

## 功能

- 四张背景图自动轮播；手机端不显示圆点和左右按钮
- 研究方向采用两列卡片，可从文本文件维护内容
- 点击头像复制邮箱，桌面端悬停显示联系气泡
- 简历在手机端按 900px 桌面版式整体缩放，呈现完整 PDF 页面视角
- FastAPI 提供静态页面与健康检查接口

## 本地运行

```powershell
python -m pip install -r backend/requirements.txt
backend/start-fastapi.bat
```

打开 `http://127.0.0.1:8000/`。

## 自定义

1. 在 `frontend/index.html` 和 `frontend/jianli.html` 中替换姓名、联系方式、简历内容与 GitHub 地址。
2. 替换 `frontend/static/avatar-placeholder.svg` 和 `logo-placeholder.svg`。
3. 修改 `frontend/static/research-directions.txt` 更新研究方向。
4. 将 `frontend/static/756.jpg`、`ban01.jpg`、`chdt.jpg`、`54qp.jpg` 替换为你有权使用的图片。

公开部署前请再次检查个人信息、服务器地址、密钥、口令和日志文件。
