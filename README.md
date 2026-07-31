# Resume Document Webpage

一个可自行替换内容的个人主页与简历网页模板，包含四图自动轮播、研究方向卡片、密码保护的两页 A4 简历，以及桌面/手机适配。

## 功能

- 四张背景图自动轮播；手机端不显示圆点和左右按钮
- 研究方向采用两列卡片，可从文本文件维护内容
- 点击头像复制邮箱，桌面端悬停显示联系气泡
- 密码使用 PBKDF2-SHA256、随机盐和 600,000 次迭代保存，不存储明文
- 每次重新打开简历都必须再次输入密码；访问凭证仅供一次简历请求使用
- 同一 IP 在 24 小时内连续输错 5 次后，整个网站对该 IP 锁定 24 小时
- 简历保持两张 A4 版式；手机端按整页比例缩放，打印调用浏览器原生 A4 打印逻辑
- 返回首页和打印按钮分别显示在简历左下角和右下角
- FastAPI 提供静态页面与健康检查接口

## 本地运行

```powershell
python -m pip install -r backend/requirements.txt
backend/start-fastapi.bat
```

首次启动前，交互式设置密码哈希：

```powershell
python backend/security_admin.py set-password
backend/start-fastapi.bat
```

脚本只写入 `backend/.resume_access_hash`，不会保存明文密码。哈希文件和封禁数据库均已加入 `.gitignore`。然后打开 `http://127.0.0.1:8000/`。

如果需要解除某个 IP 的封禁或错误计数：

```powershell
python backend/security_admin.py unblock 192.0.2.10
```

使用 `unblock --all` 可以清除全部封禁和错误计数。公开部署时建议通过 HTTPS 提供服务。

## 自定义

1. 在 `frontend/index.html` 和 `frontend/jianli.html` 中替换姓名、联系方式、简历内容与 GitHub 地址。
2. 替换 `frontend/static/avatar-placeholder.svg`、`logo-placeholder.svg` 以及 `frontend/resume-assets/` 中的简历图片。
3. 修改 `frontend/static/research-directions.txt` 更新研究方向。
4. 将 `frontend/static/756.jpg`、`ban01.jpg`、`chdt.jpg`、`54qp.jpg` 替换为你有权使用的图片。

公开部署前请再次检查个人信息、服务器地址、密钥、口令和日志文件。
