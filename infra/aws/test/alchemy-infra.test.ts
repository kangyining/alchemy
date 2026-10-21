import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { AlchemyInfraStack } from '../lib/alchemy-infra-stack';

test('chat host uses the monorepo checkout and encrypted storage', () => {
  const template = Template.fromStack(new AlchemyInfraStack(new cdk.App(), 'TestStack'));
  template.resourceCountIs('AWS::EC2::Instance', 1);
  template.resourceCountIs('AWS::EC2::NatGateway', 0);
  template.hasResourceProperties('AWS::EC2::Instance', {
    InstanceType: 't4g.large',
    BlockDeviceMappings: Match.arrayWith([Match.objectLike({
      Ebs: Match.objectLike({ Encrypted: true, VolumeType: 'gp3' }),
    })]),
  });
  const content = JSON.stringify(template.toJSON());
  expect(content).toContain('github.com/kangyining/alchemy.git');
  expect(content).toContain('WorkingDirectory=/opt/alchemy/apps/librechat');
  expect(content).not.toContain('github.com//lynx-canadensis/LibreChat.git');
});
