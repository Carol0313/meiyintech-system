# 镁印制版下单系统 - 代码发布 SOP（标准操作流程）

> 适用场景：本地开发完成后，将代码更新到生产/测试服务器  
> 工具：Xshell（SSH）、Git、WinSCP（备选）

---

## 一、前置要求

### 1.1 本地环境
- 已安装 Git
- 项目已关联远程仓库（当前：`https://github.com/Carol0313/meiyintech-system.git`）
- 已配置 Git 用户名和邮箱

### 1.2 服务器环境
- 服务器项目目录：`/home/magnesium/magnesium_order_platform`
- 服务器已配置 systemd 服务：`magnesium`
- 服务器已配置 Nginx

---

## 二、方案选择

| 方案 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| **方案A：Git 发布（推荐）** | 绝大多数改动 | 可追溯、可回滚、不易遗漏文件 | 需要会基础 Git 命令 |
| **方案B：手动上传（应急）** | 紧急小改动、Git 不可用 | 简单直接 | 易遗漏文件、无法回滚 |

---

## 三、方案A：Git 发布流程（标准流程）

### 步骤1：本地开发完成，提交代码

在本地项目根目录执行：

```bash
# 查看改了哪些文件
git status

# 添加所有改动到暂存区
git add .

# 提交并写清楚改动说明（英文或中文均可，但要能看懂）
git commit -m "feat: 修改全局字体为政务网风格"

# 推送到 GitHub
git push origin master
```

> ⚠️ **提交规范建议**：
> - `feat:` 新功能
> - `fix:` 修复 bug
> - `docs:` 文档更新
> - `style:` 样式调整（字体、颜色、布局）
> - `refactor:` 代码重构

---

### 步骤2：连接服务器并更新

用 Xshell 登录服务器，执行：

```bash
# 进入项目目录
cd /home/magnesium/magnesium_order_platform

# 拉取最新代码
git pull origin master

# 执行一键更新脚本
sudo bash deploy/update.sh
```

`update.sh` 会自动完成：
1. 安装新依赖（requirements.txt 有变化时）
2. 执行数据库迁移（有模型变更时）
3. 收集静态文件
4. 重启 Gunicorn 和 Nginx

---

### 步骤3：验证发布结果

```bash
# 查看服务是否正常运行
sudo systemctl status magnesium

# 查看最近是否有报错
sudo tail -n 30 /var/log/gunicorn/magnesium_error.log

# 打开浏览器访问网站，确认改动已生效
```

---

### 步骤4：如果发布失败，回滚到上一版本

```bash
cd /home/magnesium/magnesium_order_platform

# 查看提交历史，找到上一个正常版本的 commit ID
git log --oneline -10

# 回滚到指定版本（把 xxxxxx 替换成实际的 commit ID）
git reset --hard xxxxxx

# 重新执行更新
sudo bash deploy/update.sh
```

---

## 四、方案B：手动上传流程（应急方案）

> 仅用于紧急修复或 Git 无法使用的情况

### 步骤1：打包本地改动文件

不要上传整个项目，只上传改动的文件。例如：

```
templates/base.html          ← 改了这个
static/css/custom.css        ← 改了这个
```

把这些文件打包成 `update_20240603.zip`

---

### 步骤2：上传到服务器

用 **WinSCP**（比 Xshell 自带的上传更好用）：
1. 打开 WinSCP，连接服务器
2. 进入 `/home/magnesium/magnesium_order_platform`
3. 按对应目录结构上传文件（不要传错目录）

---

### 步骤3：服务器执行更新

用 Xshell 登录服务器：

```bash
cd /home/magnesium/magnesium_order_platform

# 激活虚拟环境
source venv/bin/activate

# 加载环境变量
export $(cat .env | xargs)

# 如果改了模型，执行迁移
python manage.py migrate

# 如果改了静态文件，重新收集
python manage.py collectstatic --noinput

# 重启服务
sudo systemctl restart magnesium
sudo systemctl reload nginx

# 验证状态
sudo systemctl status magnesium
```

---

## 五、发布检查清单（每次发布前必看）

- [ ] 本地改动已测试通过（至少跑一遍相关页面）
- [ ] `git status` 确认没有遗漏文件
- [ ] commit message 写清楚了改动内容
- [ ] 如果是数据库模型改动，确认已生成 migration 文件
- [ ] 如果是新增依赖，确认已写入 `requirements.txt`
- [ ] 发布后浏览器验证改动已生效
- [ ] 发布后检查日志是否有报错

---

## 六、常见错误处理

### 错误1：`git pull` 提示冲突

```bash
# 先查看冲突文件
git status

# 如果想放弃服务器上的本地改动，强制同步远程
git fetch origin
git reset --hard origin/master

# 然后重新执行更新
sudo bash deploy/update.sh
```

### 错误2：静态文件没生效（CSS/JS 还是旧的）

```bash
cd /home/magnesium/magnesium_order_platform
source venv/bin/activate
export $(cat .env | xargs)
python manage.py collectstatic --noinput
sudo systemctl reload nginx
```

### 错误3：数据库迁移失败

```bash
# 查看具体错误
python manage.py migrate

# 如果是 migration 冲突，可尝试假迁移（仅修复表结构记录，不实际改表）
python manage.py migrate --fake 应用名 迁移文件名
```

### 错误4：服务启动失败（502 Bad Gateway）

```bash
# 查看详细错误
sudo tail -n 50 /var/log/gunicorn/magnesium_error.log

# 手动测试启动
cd /home/magnesium/magnesium_order_platform
source venv/bin/activate
export $(cat .env | xargs)
gunicorn -c deploy/gunicorn.conf.py magnesium_order_platform.wsgi:application
```

---

## 七、推荐工具安装

| 工具 | 用途 | 下载地址 |
|------|------|---------|
| **Git** | 版本控制 | https://git-scm.com/download/win |
| **WinSCP** | SFTP 文件上传（应急用） | https://winscp.net/eng/download.php |
| **VS Code** | 代码编辑 + 内置 Git | 已安装 |

---

## 八、快速参考卡片（建议贴到桌面）

```
【本地】
git add .
git commit -m "描述"
git push origin master

【服务器】
cd /home/magnesium/magnesium_order_platform
git pull origin master
sudo bash deploy/update.sh

【验证】
sudo systemctl status magnesium
sudo tail -n 20 /var/log/gunicorn/magnesium_error.log
```

---

**文档版本**：v1.0  
**最后更新**：2026-06-03  
**适用项目**：镁印制版下单系统（meiyintech-system）
