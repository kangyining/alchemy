import * as cdk from 'aws-cdk-lib/core';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';


export interface InfinityCapitalChatProps {
  /**
   * VPC where the EC2 instance will be deployed
   */
  vpc: ec2.IVpc;
  /**
   * Instance type for the EC2 instance
   * @default t4g.large (8 GiB RAM)
   */
  instanceType?: ec2.InstanceType;
}

export class InfinityCapitalChat extends Construct {
  public readonly instance: ec2.Instance;
  public readonly elasticIp: ec2.CfnEIP;
  public readonly securityGroup: ec2.SecurityGroup;

  constructor(scope: Construct, id: string, props: InfinityCapitalChatProps) {
    super(scope, id);

    // Security group to allow HTTP, HTTPS, and SSH access
    this.securityGroup = new ec2.SecurityGroup(this, 'InfinityCapitalChatSecurityGroup', {
      vpc: props.vpc,
      securityGroupName: 'infinity-capital-chat-sg',
      description: 'Security group for InfinityCapitalChat application EC2 instance',
      allowAllOutbound: true,
    });

    // Allow HTTP traffic
    this.securityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(80),
      'Allow HTTP traffic'
    );

    // Allow HTTPS traffic
    this.securityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(443),
      'Allow HTTPS traffic'
    );

    // Allow SSH access (restrict to your IP in production)
    this.securityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(22),
      'Allow SSH access'
    );

    // Allow LibreChat application traffic
    this.securityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(3080),
      'Allow LibreChat application traffic'
    );

    const keyPair = new ec2.KeyPair(this, 'MyKeyPair', {
      keyPairName: 'infinity-capital-chat-keypair',
      format: ec2.KeyPairFormat.PEM,
    });
    

    // IAM role for EC2 instance
    const role = new iam.Role(this, 'InfinityCapitalChatInstanceRole', {
      roleName: 'infinity-capital-chat-instance-role',
      assumedBy: new iam.ServicePrincipal('ec2.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonSSMManagedInstanceCore'),
      ],
    });

    // IAM policy for SSM Parameter Store
    role.addToPolicy(new iam.PolicyStatement({
      actions: ['ssm:GetParameter'],
      resources: ['arn:aws:ssm:*:*:parameter/infinity-capital-chat/github-token'],
    }));

    // User data script to install Docker and Docker Compose
    const userData = ec2.UserData.forLinux();
    userData.addCommands(
      // -------------------------------------------
      // Wait for dpkg / apt locks
      // -------------------------------------------
      'echo "Waiting for apt/dpkg locks..."',
      'while sudo fuser /var/lib/dpkg/lock >/dev/null 2>&1; do echo "dpkg locked..."; sleep 3; done',
    
      // -------------------------------------------
      // Update apt and install base tools
      // -------------------------------------------
      'apt-get update -y',
      'apt-get install -y unzip curl git docker.io docker-compose nginx certbot python3-certbot-nginx',
    
      // -------------------------------------------
      // Install AWS CLI v2 (ARM64 version for t4g*)
      // -------------------------------------------
      'echo "Installing AWS CLI v2..."',
      'curl "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o "awscliv2.zip"',
      'unzip awscliv2.zip',
      './aws/install',
    
      // -------------------------------------------
      // Make sure Docker is running
      // -------------------------------------------
      'systemctl enable docker',
      'systemctl start docker',
    
      // -------------------------------------------
      // Retrieve token from SSM
      // -------------------------------------------
      'echo "Fetching GitHub token from SSM..."',
      'TOKEN=$(aws ssm get-parameter --name /infinity-capital-chat/github-token --with-decryption --query Parameter.Value --output text --region us-east-1)',
    
      // -------------------------------------------
      // Clone the repository
      // -------------------------------------------
      'git clone https://$TOKEN@github.com/kangyining/alchemy.git /opt/alchemy',
      'git -C /opt/alchemy remote set-url origin https://github.com/kangyining/alchemy.git',
      'unset TOKEN',
      'cd /opt/alchemy/apps/librechat',
      'docker-compose pull',

      // -------------------------------------------
      // Create systemd service for docker-compose
      // -------------------------------------------
      'cat > /etc/systemd/system/librechat.service << EOF',
      '[Unit]',
      'Description=LibreChat Docker Compose Application',
      'Requires=docker.service',
      'After=docker.service',
      '',
      '[Service]',
      'Type=oneshot',
      'RemainAfterExit=yes',
      'WorkingDirectory=/opt/alchemy/apps/librechat',
      'ExecStart=/usr/bin/docker-compose up -d',
      'ExecStop=/usr/bin/docker-compose down',
      'ExecReload=/usr/bin/docker-compose pull && /usr/bin/docker-compose up -d',
      'TimeoutStartSec=0',
      '',
      '[Install]',
      'WantedBy=multi-user.target',
      'EOF',

      // -------------------------------------------
      // Enable and start the systemd service
      // -------------------------------------------
      'systemctl daemon-reload',
      'systemctl enable librechat.service',
      'systemctl start librechat.service',

      // -------------------------------------------
      // Configure Nginx reverse proxy
      // -------------------------------------------
      'echo "Configuring Nginx reverse proxy..."',
      'cat > /etc/nginx/sites-available/alchemy-solutions.co << NGINXEOF',
      'server {',
      '    listen 80;',
      '    server_name alchemy-solutions.co www.alchemy-solutions.co;',
      '',
      '    location / {',
      '        client_max_body_size 50M;',
      '        proxy_pass http://127.0.0.1:3080;',
      '        proxy_http_version 1.1;',
      '        proxy_set_header Upgrade \\$http_upgrade;',
      '        proxy_set_header Connection "upgrade";',
      '        proxy_set_header Host \\$host;',
      '        proxy_set_header X-Real-IP \\$remote_addr;',
      '        proxy_set_header X-Forwarded-For \\$proxy_add_x_forwarded_for;',
      '        proxy_set_header X-Forwarded-Proto \\$scheme;',
      '        proxy_cache_bypass \\$http_upgrade;',
      '        proxy_read_timeout 86400;',
      '    }',
      '}',
      'NGINXEOF',

      // -------------------------------------------
      // Enable nginx site and restart
      // -------------------------------------------
      'ln -sf /etc/nginx/sites-available/alchemy-solutions.co /etc/nginx/sites-enabled/',
      'rm -f /etc/nginx/sites-enabled/default',
      'systemctl enable nginx',
      'systemctl restart nginx',

      // -------------------------------------------
      // Obtain SSL certificate (will retry if DNS not ready)
      // -------------------------------------------
      'echo "Attempting to obtain SSL certificate..."',
      'for i in 1 2 3 4 5; do',
      '  certbot --nginx -d alchemy-solutions.co -d www.alchemy-solutions.co --non-interactive --agree-tos --email admin@alchemy-solutions.co --redirect && break',
      '  echo "Certbot attempt $i failed, retrying in 60 seconds..."',
      '  sleep 60',
      'done',
    );

    // Create EC2 instance
    const instanceType = props.instanceType || ec2.InstanceType.of(
      ec2.InstanceClass.T4G,
      ec2.InstanceSize.LARGE
    );

    this.instance = new ec2.Instance(this, 'InfinityCapitalChatInstance', {
      vpc: props.vpc,
      instanceName: 'infinity-capital-chat',
      instanceType,
      machineImage: ec2.MachineImage.fromSsmParameter(
        '/aws/service/canonical/ubuntu/server/24.04/stable/current/arm64/hvm/ebs-gp3/ami-id'
      ),
      securityGroup: this.securityGroup,
      role,
      userData,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PUBLIC,
      },
      keyPair,
      blockDevices: [
        {
          deviceName: '/dev/sda1',
          volume: ec2.BlockDeviceVolume.ebs(50, {
            volumeType: ec2.EbsDeviceVolumeType.GP3,
            encrypted: true,
          }),
        },
      ],
    });

    // Create Elastic IP
    this.elasticIp = new ec2.CfnEIP(this, 'InfinityCapitalChatElasticIP', {
      domain: 'vpc',
      instanceId: this.instance.instanceId,
      tags: [{ key: 'Name', value: 'infinity-capital-chat-eip' }],
    });

    // Outputs
    new cdk.CfnOutput(this, 'InfinityCapitalChatInstanceId', {
      value: this.instance.instanceId,
      description: 'InfinityCapitalChat EC2 Instance ID',
    });

    new cdk.CfnOutput(this, 'InfinityCapitalChatElasticIPOutput', {
      value: this.elasticIp.ref,
      description: 'Elastic IP address of the InfinityCapitalChat EC2 instance',
    });

    new cdk.CfnOutput(this, 'InfinityCapitalChatPublicIP', {
      value: this.instance.instancePublicIp,
      description: 'Public IP address of the InfinityCapitalChat EC2 instance',
    });

    new cdk.CfnOutput(this, 'InfinityCapitalChatSSHCommand', {
      value: `ssh -i your-key.pem ubuntu@${this.elasticIp.ref}`,
      description: 'SSH command to connect to the InfinityCapitalChat instance',
    });

    new cdk.CfnOutput(this, 'InfinityCapitalChatDockerComposeLocation', {
      value: '/opt/alchemy/apps/librechat',
      description: 'LibreChat Docker Compose directory in the monorepo',
    });
  }
}

