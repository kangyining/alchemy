import * as cdk from 'aws-cdk-lib/core';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';
import { InfinityCapitalChat, InfinityCapitalChatProps } from './inifinity-capital-chat/main';

export interface AlchemyInfraStackProps extends cdk.StackProps {
  /**
   * Instance type for the InfinityCapitalChat EC2 instance
   * @default t4g.large (8 GiB RAM)
   */
  infinityCapitalChatInstanceType?: ec2.InstanceType;
}

export class AlchemyInfraStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: AlchemyInfraStackProps) {
    super(scope, id, props);

    // Create a shared VPC for all Alchemy applications
    const vpc = new ec2.Vpc(this, 'AlchemySharedVPC', {
      vpcName: 'alchemy-shared-vpc',
      maxAzs: 2,
      natGateways: 0, // No NAT gateway needed for public instances
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
        },
      ],
    });

    // Deploy InfinityCapitalChat application
    new InfinityCapitalChat(this, 'InfinityCapitalChat', {
      vpc,
      instanceType: props?.infinityCapitalChatInstanceType,
    });
  }
}
