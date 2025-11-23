# Alchemy Infrastructure

CDK TypeScript project for managing Alchemy infrastructure across dev and prod environments.

The `cdk.json` file tells the CDK Toolkit how to execute your app.

## Useful Commands

### Build & Test
* `npm run build`   compile TypeScript to JavaScript
* `npm run watch`   watch for changes and compile
* `npm run test`    perform the jest unit tests

### Development Environment
* `npm run deploy:dev`  deploy dev stack to AWS
* `npm run diff:dev`    compare deployed dev stack with current state
* `npm run synth:dev`   emit the synthesized CloudFormation template for dev

### Production Environment
* `npm run deploy:prod`  deploy prod stack to AWS
* `npm run diff:prod`    compare deployed prod stack with current state
* `npm run synth:prod`   emit the synthesized CloudFormation template for prod

## Getting Started

### Prerequisites

1. Install Node.js and npm
2. Install AWS CDK CLI: `npm install -g aws-cdk`
3. Install AWS CLI and ensure it's on your PATH

### Environment Setup

This project uses separate AWS profiles for dev and prod environments, which correspond to different AWS accounts.

#### Configure AWS Profiles

**Development Environment:**
```bash
aws configure --profile alchemy-dev
```
- Access Key ID: Generated in AWS Console → IAM → Users → [Your User] → Security credentials
- Secret Access Key: Generated in AWS Console → IAM → Users → [Your User] → Security credentials
- Default region: `us-east-1`
- Default output format: `json`

**Production Environment:**
```bash
aws configure --profile alchemy-prod
```
- Access Key ID: Generated in AWS Console → IAM → Users → [Your User] → Security credentials
- Secret Access Key: Generated in AWS Console → IAM → Users → [Your User] → Security credentials
- Default region: `us-west-2`
- Default output format: `json`

> **Note:** Dev and prod use different AWS accounts. Make sure you have the appropriate IAM credentials for each account.

### First Deployment

1. Build the project: `npm run build`
2. Bootstrap CDK (one-time setup per account/region):
   ```bash
   npx cdk bootstrap --profile alchemy-dev
   npx cdk bootstrap --profile alchemy-prod
   ```
3. Review changes: `npm run diff:dev` or `npm run diff:prod`
4. Deploy: `npm run deploy:dev` or `npm run deploy:prod`
