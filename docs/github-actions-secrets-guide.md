# GitHub Actions Secrets 说明

> 主题：`Repository secrets`、`Environment secrets`、`Organization secrets` 的区别、使用场景和推荐实践
> 适用场景：GitHub Actions 工作流配置

参考官方文档：

- GitHub Docs: Using secrets in GitHub Actions  
  https://docs.github.com/actions/reference/encrypted-secrets?tool=webui
- GitHub Docs: Secrets  
  https://docs.github.com/en/actions/concepts/security/secrets
- GitHub Docs: Deployments and environments  
  https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments
- GitHub Docs: Variables reference  
  https://docs.github.com/en/actions/reference/workflows-and-actions/variables

## 1. 先说结论

这三类 secrets 的区别，本质上是 **作用域** 和 **治理方式** 不同：

- `Repository secrets`
  - 作用于单个仓库
  - 最常用
  - 适合这个仓库专用的密钥

- `Environment secrets`
  - 作用于仓库内的某个环境，例如 `staging`、`production`
  - 适合“同一个仓库，不同部署环境用不同密钥”
  - 可以和审批、保护规则绑定

- `Organization secrets`
  - 作用于组织级别
  - 可以共享给多个仓库
  - 适合跨仓库复用的统一密钥

## 2. 三者的核心区别

| 类型 | 作用范围 | 典型用途 | 优点 | 风险/限制 |
|------|----------|----------|------|-----------|
| Repository secrets | 单个仓库 | 仓库专属 API Key、Token | 简单直接 | 仓库一多会重复维护 |
| Environment secrets | 单仓库内某个环境 | `staging`/`production` 分环境密钥 | 支持环境保护和审批 | 只有引用该 environment 的 job 才能拿到 |
| Organization secrets | 组织内多个仓库 | 多仓库共用的云平台、监控、通知密钥 | 集中治理、减少重复 | 权限面更大，配置不当容易过宽 |

## 3. Repository secrets

## 3.1 是什么

仓库级密钥，存在：

- `Repository -> Settings -> Secrets and variables -> Actions`

只能给当前仓库里的 GitHub Actions workflow 使用。

## 3.2 适合什么场景

适合：

- 这个仓库专用的第三方 API key
- 不需要按环境区分的密钥
- 先快速跑通自动化

例如：

- `PRODUCTHUNT_DEVELOPER_TOKEN`
- `NULLCLAW_API_KEY`
- `NULLCLAW_BASE_URL`

对 AIpulse 这种单仓项目，默认最适合先用这个。

## 3.3 优点

- 最容易理解
- 配置最简单
- 最适合单仓起步

## 3.4 缺点

- 如果组织里很多仓库都要用同一个 secret，会重复维护
- 无法天然区分 `staging` 和 `production`

## 4. Environment secrets

## 4.1 是什么

环境级密钥，存在：

- `Repository -> Settings -> Environments -> 某个环境 -> Environment secrets`

只有当 workflow job 显式声明了：

```yaml
environment: production
```

对应环境的 secret 才能被该 job 读取。

## 4.2 适合什么场景

适合：

- 同一个仓库同时有 `staging` 和 `production`
- 不同环境使用不同账号、不同 key、不同域名
- 希望部署到生产前加审批

例如：

- `NETLIFY_AUTH_TOKEN`
- `CLOUDFLARE_API_TOKEN`
- `DATABASE_URL`

在 `staging` 和 `production` 中分别不同。

## 4.3 最大价值

它不仅是“存一份 secret”，更重要的是它和 **部署环境治理** 绑定：

- 可以设置 required reviewers
- 可以设置等待时间
- 可以限制哪些分支能部署

这意味着：

- workflow 即使跑到部署步骤
- 没通过环境审批
- 也拿不到该 environment 的 secret

这是它和 repository secrets 最大的区别。

## 4.4 限制和注意点

- 只有引用对应 environment 的 job 才能访问
- 对私有仓库是否可用，和 GitHub 计划有关
- 如果 workflow 根本没写 `environment: xxx`，这些 secrets 等于不存在

## 5. Organization secrets

## 5.1 是什么

组织级密钥，存在：

- `Organization -> Settings -> Secrets and variables -> Actions`

可以授权给：

- 全部仓库
- 私有仓库
- 选定仓库

## 5.2 适合什么场景

适合：

- 多个仓库共用同一个服务凭据
- 想集中治理
- 想统一轮换 secret

例如：

- 企业统一的 Sentry token
- 多个仓库都要用的通知 webhook
- 统一的云账号凭据

## 5.3 优点

- 一处更新，多仓库生效
- 减少重复维护
- 适合平台团队或组织级治理

## 5.4 风险

如果给得太宽，会有两个问题：

1. 访问范围过大  
2. 某个仓库被误配置时，可能拿到本不该拿到的 secret

所以组织级 secret 最好配：

- 最小可见范围
- 尽量使用 `selected repositories`

不要默认全开给整个组织。

## 6. 什么时候用哪一种

## 6.1 适合单仓起步的策略

如果你是单个项目、先求跑通：

- 优先 `Repository secrets`

这是最简单的。

## 6.2 适合多环境部署的策略

如果你有：

- `staging`
- `production`

那部署密钥最好放：

- `Environment secrets`

而不是把所有环境值都堆到 repository secrets 里。

## 6.3 适合多仓治理的策略

如果你已经有多个仓库共享同一个凭据：

- 优先 `Organization secrets`

但要限制到特定仓库，不要默认全组织放开。

## 7. 一个实际判断方法

可以用这三个问题判断：

### 问题 1

这个 secret 是不是只给一个仓库用？

- 是：`Repository secret`
- 否：看问题 2

### 问题 2

这个 secret 是不是同一个仓库里，不同环境值不同？

- 是：`Environment secret`
- 否：看问题 3

### 问题 3

这个 secret 是不是多个仓库共用同一个值？

- 是：`Organization secret`

## 8. Secrets 和 Variables 的区别

这是另一个很容易混淆的点。

### Secrets

适合：

- API Key
- Token
- 密码
- 私密 URL

特点：

- 加密存储
- 日志里会尽量掩码
- 用 `secrets.NAME` 读取

### Variables

适合：

- 非敏感配置
- 模型名
- 环境名
- 普通开关值

特点：

- 不是密钥
- 用 `vars.NAME` 读取

例如：

- `NULLCLAW_MODEL` 更适合 variable
- `NULLCLAW_API_KEY` 必须是 secret

## 9. 优先级与覆盖规则

官方文档对 variables 给出的规则是：

- 同名变量如果同时存在于 organization、repository、environment
- **更具体的层级优先**

也就是一般可理解为：

- `environment` 覆盖 `repository`
- `repository` 覆盖 `organization`

但需要注意：

- environment 变量是在 job 执行时才可用
- 它不会像普通 `env` 那样在所有解析阶段都覆盖

所以在写 workflow 时，要区分：

- `vars`
- `env`
- `secrets`

不要把它们混成一套心智。

## 10. AIpulse 适合怎么配

对 AIpulse 当前阶段，推荐这样：

### Repository secrets

放这些：

- `PRODUCTHUNT_DEVELOPER_TOKEN`
- `PRODUCTHUNT_CLIENT_ID`
- `PRODUCTHUNT_CLIENT_SECRET`
- `NULLCLAW_API_KEY`
- `NULLCLAW_BASE_URL`

### Repository variables

放这些：

- `NULLCLAW_MODEL`

## 11. 以后什么时候升级到 Environment secrets

当你出现这些需求时，再上 environment：

- `preview` / `production` 分开部署
- 生产部署要审批
- 不同环境使用不同 Netlify / Cloudflare / API 凭据

那时建议：

- `preview` 一套 environment secrets
- `production` 一套 environment secrets

## 12. 以后什么时候升级到 Organization secrets

当你出现这些情况时，再上 organization：

- 你有多个仓库
- 多个仓库共用同一个第三方服务凭据
- 你不想每个仓库都手动改一次

## 13. 常见误区

### 误区 1：把所有东西都放 secrets

不是。  
像模型名、环境名、开关值，更适合放 variables。

### 误区 2：Environment secrets 会自动生效

不会。  
workflow job 必须显式引用对应 environment。

### 误区 3：Organization secrets 一定更高级

不一定。  
对于单仓项目，repository secrets 往往更简单、更安全。

### 误区 4：Repository secrets 和 Environment secrets 二选一

也不是。  
常见做法是混合：

- 仓库通用 secret 放 repository
- 部署相关 secret 放 environment

## 14. 推荐实践

最实用的策略是：

1. 单仓起步：先用 repository secrets
2. 多环境部署：把部署类凭据迁到 environment secrets
3. 多仓复用：再把跨仓通用凭据提升到 organization secrets
4. 始终坚持最小权限

## 15. 一句话总结

- **Repository secrets**：单仓最常用
- **Environment secrets**：分环境部署和审批控制
- **Organization secrets**：多仓统一治理

对 AIpulse 当前阶段，最合适的是：

- 先以 `Repository secrets + Repository variables` 为主
- 等你后面有 `staging / production` 再引入 `Environment secrets`
