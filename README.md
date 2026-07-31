# Resume Document Webpage

一个可自行替换内容的个人主页与简历网页模板，包含四图自动轮播、研究方向卡片、密码保护的两页 A4 简历，以及桌面/手机适配。

## 功能

- 四张背景图自动轮播；手机端不显示圆点和左右按钮
- 研究方向采用两列卡片，可从文本文件维护内容
- 点击头像复制邮箱，桌面端悬停显示联系气泡
- 简历使用服务器端密码验证，口令不会写入前端源码
- 简历保持两张 A4 版式；手机端按整页比例缩放，打印调用浏览器原生 A4 打印逻辑
- 返回首页和打印按钮以悬浮胶囊样式显示在简历末尾
- FastAPI 提供静态页面与健康检查接口

## 本地运行

```powershell
python -m pip install -r backend/requirements.txt
backend/start-fastapi.bat
```

设置简历访问密码后再启动服务：

```powershell
$env:RESUME_ACCESS_CODE = "请替换为自己的密码"
backend/start-fastapi.bat
```

也可以把密码单独写入 `backend/.resume_access_code`。该文件已加入 `.gitignore`，请勿提交。然后打开 `http://127.0.0.1:8000/`。

## 自定义

1. 在 `frontend/index.html` 和 `frontend/jianli.html` 中替换姓名、联系方式、简历内容与 GitHub 地址。
2. 替换 `frontend/static/avatar-placeholder.svg`、`logo-placeholder.svg` 以及 `frontend/resume-assets/` 中的简历图片。
3. 修改 `frontend/static/research-directions.txt` 更新研究方向。
4. 将 `frontend/static/756.jpg`、`ban01.jpg`、`chdt.jpg`、`54qp.jpg` 替换为你有权使用的图片。

公开部署前请再次检查个人信息、服务器地址、密钥、口令和日志文件。
