#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib/core';
import { AlchemyInfraStack } from '../lib/alchemy-infra-stack';

const app = new cdk.App();

new AlchemyInfraStack(app, 'alchemy-infra-dev', {
  env: { account: '088332244851', region: 'us-east-1' },
});

// new AlchemyInfraStack(app, 'alchemy-infra-prod', {
//   env: { account: '088332244851', region: 'us-west-2' },
// });
