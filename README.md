# yx-token 组织公共配置

## 通知

组织统一的通知渠道配置在本仓库，目前支持**飞书自定义机器人**和**邮件（SMTP）**。各项目在需要时（例如发版成功后）触发本仓库的 [`Notify`](.github/workflows/notify.yml) workflow，按这里已配置的渠道发送；一个渠道都没配置时直接跳过，不算失败。某个渠道配置不完整或发送失败时，其余渠道照常发送，本次运行标为失败。

> 为什么不用组织级 Secrets：组织是 GitHub Free 套餐，私有仓库读不到组织级 Secrets 和 Variables，所以把渠道配置集中放在本仓库，由各项目触发这里的 workflow 来发送。以后升级到 Team 套餐，可以改成组织级 Secrets 加 reusable workflow。

### 配置渠道

在本仓库 Settings → Secrets and variables → Actions 中配置，**哪个渠道的必填项配齐了就启用哪个渠道**：

| 渠道 | 名称 | 类型 | 说明 |
| --- | --- | --- | --- |
| 飞书 | `FEISHU_WEBHOOK` | Secret | 必填。群设置 → 群机器人 → 添加机器人 → 自定义机器人，复制 Webhook 地址 |
| 飞书 | `FEISHU_SECRET` | Secret | 选填。机器人安全设置选择「签名校验」时填写对应密钥 |
| 邮件 | `SMTP_HOST` | Variable | 必填。例如 `smtp.feishu.cn`、`smtp.qq.com`、`smtp.163.com`、`smtp.exmail.qq.com` |
| 邮件 | `SMTP_PORT` | Variable | 选填，默认 `465`（SSL）。其他端口（一般是 `587`）使用 STARTTLS |
| 邮件 | `SMTP_USERNAME` | Variable | 必填。发件邮箱账号 |
| 邮件 | `SMTP_PASSWORD` | Secret | 必填。密码；QQ、163 等邮箱填写客户端授权码 |
| 邮件 | `SMTP_FROM` | Variable | 选填，默认等于 `SMTP_USERNAME`。可以写成 `发版通知 <bot@example.com>` |
| 邮件 | `EMAIL_TO` | Variable | 必填。收件人，多个用逗号分隔 |

也可以用命令行配置（Secret 会提示粘贴，不会留在 shell 历史里）：

```bash
gh secret set FEISHU_WEBHOOK -R yx-token/.github
gh secret set FEISHU_SECRET -R yx-token/.github

gh variable set SMTP_HOST -R yx-token/.github --body smtp.feishu.cn
gh variable set SMTP_USERNAME -R yx-token/.github --body bot@example.com
gh secret set SMTP_PASSWORD -R yx-token/.github
gh variable set EMAIL_TO -R yx-token/.github --body "a@example.com,b@example.com"
```

注意：

- 飞书机器人的安全设置不要用「IP 白名单」，GitHub 托管运行器的出口 IP 不固定；用「自定义关键词」时，标题或正文里必须包含关键词。
- GitHub 托管运行器封禁了 25 端口，邮件请用 465 或 587。

### 测试

配好后在本仓库 Actions → Notify → Run workflow 手动发一条，或者：

```bash
gh workflow run notify.yml -R yx-token/.github -f title="通知测试" -f content="**渠道**：测试"
gh run watch -R yx-token/.github "$(gh run list -R yx-token/.github -w notify.yml -L 1 --json databaseId -q '.[0].databaseId')"
```

### 项目接入

1. **创建触发用的 token**（整个组织共用一个即可）：打开 <https://github.com/settings/personal-access-tokens/new> 创建 fine-grained token：
   - Resource owner 选 `yx-token`；
   - Repository access 选 Only select repositories → `yx-token/.github`；
   - Permissions → Repository permissions → **Actions** 选 Read and write，其他保持默认。

   这个 token 只能触发本仓库的 workflow，不能读写代码、也拿不到渠道密钥。如果组织开启了 token 审批，需要组织管理员在 Settings → Personal access tokens → Pending requests 中批准。token 过期后各项目的通知会失败，届时重新生成并更新各项目的 secret。

2. **在项目中配置**该 token：

   ```bash
   gh secret set NOTIFY_DISPATCH_TOKEN -R yx-token/<项目>
   ```

   没有配置 `NOTIFY_DISPATCH_TOKEN` 的项目会跳过通知。

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
           gh workflow run notify.yml -R "${GITHUB_REPOSITORY_OWNER}/.github" \
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
