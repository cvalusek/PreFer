# IAM for the AMI build (GitHub OIDC)

The `build-aws.yml` workflow's `ami` job assumes an IAM role via GitHub OIDC (no
long-lived keys). One-time setup in your AWS account:

1. **OIDC provider** (if not already added): provider URL
   `https://token.actions.githubusercontent.com`, audience `sts.amazonaws.com`.

2. **Role**: Create role → **Custom trust policy** → paste
   [github-actions-trust-policy.json](github-actions-trust-policy.json), then
   replace `ACCOUNT_ID` with your 12-digit account id. The `:sub` is scoped to
   `repo:cvalusek/PreFer:ref:refs/heads/main` — only the main branch can assume
   the role (matches build-aws.yml, which runs on push/dispatch to main). The
   sub uses the full git ref, NOT a bare branch name like `:main`.

   To allow any branch/tag instead, use StringLike with
   `repo:cvalusek/PreFer:*`.

3. **Permissions**: attach [packer-permissions-policy.json](packer-permissions-policy.json)
   (HashiCorp's documented minimal EBS-builder set + `ssm:GetParameters` for the
   DLAMI base lookup). Quicker but broader alternative: the AWS-managed
   `AmazonEC2FullAccess` + `AmazonSSMReadOnlyAccess`.

4. Copy the **role ARN** into the repo secret **`AWS_PACKER_ROLE_ARN`**.

The role lives in your account and is not shareable/public — anyone forking this
repo creates their own.
