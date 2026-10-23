# yx-token 组织公共配置

## 通知

组织统一的通知渠道配置在本仓库，目前支持**飞书自定义机器人**和**邮件（SMTP）**。各项目在需要时（例如发版成功后）触发本仓库的 [`Notify`](.github/workflows/notify.yml) workflow，按这里已配置的渠道发送；一个渠道都没配置时直接跳过，不算失败。某个渠道配置不完整或发送失败时，其余渠道照常发送，本次运行标为失败。

> 为什么不用组织级 Secrets：组织是 GitHub Free 套餐，私有仓库读不到组织级 Secrets 和 Variables，所以把渠道配置集中放在本仓库，由各项目触发这里的 workflow 来发送。以后升级到 Team 套餐，可以改成组织级 Secrets 加 reusable workflow。

### 配置项一览

配置分在两个地方：

| 配置位置 | 配置内容 | 什么时候配 |
| --- | --- | --- |
| 本仓库 `yx-token/.github` | 通知渠道：[飞书](#飞书配置在本仓库)、[邮件](#邮件配置在本仓库) | 整个组织只配一次，所有项目共用 |
| 各项目仓库，例如 `yx-token/token-market` | [`NOTIFY_DISPATCH_TOKEN`](#触发-token配置在各项目仓库) | 每个要发通知的项目各配一次 |

两处都在仓库的 **Settings → Secrets and variables → Actions** 页面。页面上有 **Secrets** 和 **Variables** 两个标签：

- 表中「类型」为 **Secret** 的，在 Secrets 标签点 New repository secret 添加。值加密保存，保存后看不到原值，日志中会被打码。
- 表中「类型」为 **Variable** 的，在 Variables 标签点 New repository variable 添加。值明文可见，方便核对。
- 本仓库是公开仓库，运行日志任何人都能看到，Variable 的值会原样打印在日志里。所以只有服务器地址、端口这类可以公开的配置用 Variable，邮箱地址都用 Secret。
- 都添加为**仓库级**（Repository secrets / Repository variables），不要加到 Environment 或组织级。组织是 Free 套餐，组织级的配置私有仓库读不到。
- 名称和类型必须和下表完全一致。放错标签页会读不到，例如把 `SMTP_HOST` 建成了 Secret，会报「缺少 SMTP_HOST」。
- 修改后立即生效，下一次通知就会用新配置。

#### 飞书：配置在本仓库

配置页面：[Secrets](https://github.com/yx-token/.github/settings/secrets/actions)

| 配置项 | 类型 | 必填 | 说明 | 示例 |
| --- | --- | --- | --- | --- |
| `FEISHU_WEBHOOK` | Secret | 是 | 飞书群 → 设置 → 群机器人 → 添加机器人 → 自定义机器人，复制 Webhook 地址 | `https://open.feishu.cn/open-apis/bot/v2/hook/xxxx` |
| `FEISHU_SECRET` | Secret | 否 | 机器人安全设置勾选「签名校验」时，填写页面上显示的密钥；没开签名校验就不配 | |

- **启用条件**：配置了 `FEISHU_WEBHOOK`。只配了 `FEISHU_SECRET` 会按配置不完整报错。
- 机器人安全设置不要用「IP 白名单」，因为 GitHub 托管运行器的出口 IP 不固定。用「自定义关键词」时，标题或正文里必须包含关键词，否则飞书会拒收。推荐用「签名校验」。

#### 邮件：配置在本仓库

配置页面：[Secrets](https://github.com/yx-token/.github/settings/secrets/actions)（`SMTP_USERNAME`、`SMTP_PASSWORD`、`SMTP_FROM`、`EMAIL_TO`）、[Variables](https://github.com/yx-token/.github/settings/variables/actions)（`SMTP_HOST`、`SMTP_PORT`）

| 配置项 | 类型 | 必填 | 说明 | 示例 |
| --- | --- | --- | --- | --- |
| `SMTP_HOST` | Variable | 是 | SMTP 服务器地址 | `smtp.feishu.cn` |
| `SMTP_PORT` | Variable | 否 | 默认 `465`（SSL）；其他端口使用 STARTTLS，一般是 `587`。25 端口被 GitHub 托管运行器封禁 | `465` |
| `SMTP_USERNAME` | Secret | 是 | 发件邮箱的登录账号 | `bot@example.com` |
| `SMTP_PASSWORD` | Secret | 是 | 发件邮箱的密码。QQ、163、飞书等邮箱需在邮箱设置中开启 SMTP，填写生成的授权码或专用密码 | |
| `SMTP_FROM` | Secret | 否 | 发件人，默认等于 `SMTP_USERNAME`。可以加显示名称，但多数邮箱要求地址和登录账号一致 | `发版通知 <bot@example.com>` |
| `EMAIL_TO` | Secret | 是 | 收件人，多个用逗号、分号或空格分隔 | `a@example.com,b@example.com` |

- **启用条件**：上表任意一项有值，就视为要启用邮件；这时 4 个必填项缺任何一个都会报错。
- 常用邮箱的 SMTP 服务器（端口都用 465）：飞书邮箱 `smtp.feishu.cn`、腾讯企业邮 `smtp.exmail.qq.com`、QQ 邮箱 `smtp.qq.com`、163 邮箱 `smtp.163.com`、Gmail `smtp.gmail.com`。

#### 触发 token：配置在各项目仓库

配置页面：`https://github.com/yx-token/<项目>/settings/secrets/actions`

| 配置项 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `NOTIFY_DISPATCH_TOKEN` | Secret | 否 | 用来触发本仓库 Notify workflow 的 fine-grained token，创建方法见[项目接入](#项目接入)第 1 步。所有项目可以共用同一个 token。不配置时该项目不发通知 |

#### 用命令行配置

Secret 会提示粘贴值，不会留在 shell 历史里：

```bash
# 本仓库：飞书
gh secret set FEISHU_WEBHOOK -R yx-token/.github
gh secret set FEISHU_SECRET -R yx-token/.github          # 开启了签名校验时

# 本仓库：邮件
gh variable set SMTP_HOST -R yx-token/.github --body smtp.feishu.cn
gh variable set SMTP_PORT -R yx-token/.github --body 465  # 可省略
gh secret set SMTP_USERNAME -R yx-token/.github
gh secret set SMTP_PASSWORD -R yx-token/.github
gh secret set SMTP_FROM -R yx-token/.github              # 可省略
gh secret set EMAIL_TO -R yx-token/.github

# 各项目仓库
gh secret set NOTIFY_DISPATCH_TOKEN -R yx-token/<项目>

# 查看已配置的项（Secret 只显示名称）
gh secret list -R yx-token/.github
gh variable list -R yx-token/.github
```

停用某个渠道时，删除该渠道的全部配置项即可，例如 `gh secret delete FEISHU_WEBHOOK -R yx-token/.github`。

### 测试

配好后在本仓库 Actions → Notify → Run workflow 手动发一条，或者：

```bash
gh workflow run notify.yml -R yx-token/.github -f title="通知测试" -f content="**渠道**：测试"
gh run watch -R yx-token/.github "$(gh run list -R yx-token/.github -w notify.yml -L 1 --json databaseId -q '.[0].databaseId')"
```

### 项目接入

1. **创建触发用的 token**（整个组织共用一个即可）：打开 <https://github.com/settings/personal-access-tokens/new> 创建 fine-grained token：
   - Resource owner 选 `yx-token`；
   - Expiration 选 No expiration（组织已关闭「细粒度 token 必须设置过期时间」的策略）；
   - Repository access 选 Only select repositories → `yx-token/.github`；
   - Permissions → Repository permissions → **Actions** 选 Read and write，其他保持默认。

   这个 token 只能触发本仓库的 workflow，不能读写代码、也拿不到渠道密钥。如果组织开启了 token 审批，需要组织管理员在 Settings → Personal access tokens → Pending requests 中批准。当前使用的 token 名为 `notify-dispatch`，永不过期；如果它被删除或重新生成，各项目的通知会失败，需要更新各项目的 secret。

2. **在项目仓库中添加 Secret** `NOTIFY_DISPATCH_TOKEN`，值为上一步的 token（见[触发 token](#触发-token配置在各项目仓库)）：

   ```bash
   gh secret set NOTIFY_DISPATCH_TOKEN -R yx-token/<项目>
   ```

   没有配置这个 Secret 的项目会跳过通知。

3. **在项目 workflow 中触发**，例如发版成功后（`needs` 指向发版的最后一个 job）：

   ```yaml
   notify:
     name: 发版通知
     needs: release
     runs-on: ubuntu-latest
     permissions: {}
     steps:
       - name: 通知组织已配置的渠道
         env:
           GH_TOKEN: ${{ secrets.NOTIFY_DISPATCH_TOKEN }}
         run: |
           if [ -z "$GH_TOKEN" ]; then
             echo "::notice::未配置 NOTIFY_DISPATCH_TOKEN，跳过发版通知"
             exit 0
           fi
           # 必须带 --ref：不带时 gh 会查询本仓库的默认分支，token 没有这个权限，触发失败
           gh workflow run notify.yml -R "${GITHUB_REPOSITORY_OWNER}/.github" --ref main \
             -f title="${GITHUB_REPOSITORY#*/} ${GITHUB_REF_NAME} 发布成功" \
             -f content="**版本**：${GITHUB_REF_NAME}"$'\n'"**发布人**：${GITHUB_ACTOR}" \
             -f url="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/releases/tag/${GITHUB_REF_NAME}" \
             -f status=success \
             -f source="$GITHUB_REPOSITORY"
   ```

   参数：

   | 参数 | 必填 | 说明 |
   | --- | --- | --- |
   | `title` | 是 | 标题，也是邮件主题 |
   | `content` | 否 | 正文，支持 `**加粗**`、`[文字](链接)`；邮件中转为纯文本 |
   | `url` | 否 | 详情链接，飞书卡片显示为「查看详情」按钮 |
   | `status` | 否 | `info`（默认，蓝色）、`success`（绿色）、`failure`（红色） |
   | `source` | 否 | 来源仓库，显示在消息底部和本仓库的运行记录名称中 |

触发是异步的：项目里的这一步只负责提交触发请求，实际发送结果看本仓库 Actions 中对应的 Notify 运行记录（名称为「来源 · 标题」）。

## 开发

```bash
python3 -m unittest discover -s scripts -v
```
