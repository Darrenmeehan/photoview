from aws_cdk import core
from aws_cdk import (core, aws_ec2 as ec2, aws_ecs as ecs,
                     aws_ecs_patterns as ecs_patterns)

from aws_cdk import aws_servicediscovery
class InfrastructureStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        vpc = ec2.Vpc(self, "MyVpc",
            # 'cidr' configures the IP range and size of the entire VPC.
            # The IP space will be divided over the configured subnets.
            cidr="10.0.0.0/21",

            # 'maxAzs' configures the maximum number of availability zones to use
            max_azs=3,

            # 'subnetConfiguration' specifies the "subnet groups" to create.
            # Every subnet group will have a subnet for each AZ, so this
            # configuration will create `3 groups × 3 AZs = 9` subnets.
            subnet_configuration=[ec2.SubnetConfiguration(
                # 'subnetType' controls Internet access, as described above.
                subnet_type=ec2.SubnetType.PUBLIC,

                # 'name' is used to name this particular subnet group. You will have to
                # use the name for subnet selection if you have more than one subnet
                # group of the same type.
                name="Ingress",

                # 'cidrMask' specifies the IP addresses in the range of of individual
                # subnets in the group. Each of the subnets in this group will contain
                # `2^(32 address bits - 24 subnet bits) - 2 reserved addresses = 254`
                # usable IP addresses.
                #
                # If 'cidrMask' is left out the available address space is evenly
                # divided across the remaining subnet groups.
                cidr_mask=24
            ), ec2.SubnetConfiguration(
                cidr_mask=24,
                name="Application",
                subnet_type=ec2.SubnetType.PRIVATE
            ), ec2.SubnetConfiguration(
                cidr_mask=28,
                name="Database",
                subnet_type=ec2.SubnetType.ISOLATED,

                # 'reserved' can be used to reserve IP address space. No resources will
                # be created for this subnet, but the IP range will be kept available for
                # future creation of this subnet, or even for future subdivision.
                reserved=True
            )
            ]
        )

        # Revisit instance sizes https://aws.amazon.com/ec2/instance-types/
        instance_type = ec2.InstanceType("t3a.medium")

        capacity_options = ecs.AddCapacityOptions(
            can_containers_access_instance_role=False,
            desired_capacity=1,
            max_capacity=1,
            min_capacity=1,
            instance_type=instance_type,
        )
        cluster = ecs.Cluster(
            self,
            "MyCluster",
            vpc=vpc,
            capacity=capacity_options,
        )
        sd_namespace = cluster.add_default_cloud_map_namespace(
            name="svc.test.local",
            vpc=vpc
        )
        aws_servicediscovery.Service(
            self,
            "svc.test.local",
            namespace=sd_namespace,
            load_balancer=True
        )
        app_port_mapping = ecs.PortMapping(
            container_port=24,
            host_port=24,
        )
        # FIXME Add in https://docs.aws.amazon.com/cdk/api/latest/python/aws_cdk.aws_ecs/ContainerDependency.html
        # https://docs.aws.amazon.com/cdk/api/latest/python/aws_cdk.aws_ecs/DockerVolumeConfiguration.html
        # https://docs.aws.amazon.com/cdk/api/latest/python/aws_cdk.aws_ecs/Secret.html
        ecs_patterns.ApplicationLoadBalancedEc2Service(self, "MyPhotoService",
            cluster=cluster,            # Required
            cpu=256,                    # Default is 256
            desired_count=1,            # Default is 1
            # task_definition=app_task_definition,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_registry("viktorstrate/photoview:1"),
                environment={
                    "MYSQL_URL": "photoview:photo-secret@tcp(db.svc.test.local)/photoview",
                    "API_LISTEN_IP": "photoview",
                    "API_LISTEN_PORT": "80",
                    "PHOTO_CACHE": "/app/cache",
                },
                enable_logging=True,
            ),
            memory_limit_mib=512,      # Default is 512
            public_load_balancer=True, # Default is False
        )

        task_definition = ecs.Ec2TaskDefinition(
            self,
            "TaskDef",
            network_mode=ecs.NetworkMode.AWS_VPC,
        )
        task_definition.add_container("DBContainer",
            image=ecs.ContainerImage.from_registry("mariadb:10.5"),
            memory_limit_mib=512,
            environment={
                "MYSQL_DATABASE": "photoview",
                "MYSQL_USER": "photoview",
                "MYSQL_PASSWORD": "photo-secret",
                "MYSQL_RANDOM_ROOT_PASSWORD": "1"
            },
            logging=ecs.AwsLogDriver(stream_prefix="PhotoviewDbContainer")
        )
        ecs_service = ecs.Ec2Service(self, "DbService",
            cluster=cluster,
            task_definition=task_definition,
            cloud_map_options=ecs.CloudMapOptions(
                cloud_map_namespace=sd_namespace,
                name="db",
            ),
        )
