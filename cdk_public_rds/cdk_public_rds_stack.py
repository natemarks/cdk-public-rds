#!/usr/bin/env python3
# pylint: disable=anomalous-backslash-in-string
""" public test
"""
from dataclasses import dataclass
import json

from aws_cdk import (
    # Duration,
    Stack,
    aws_ec2 as ec2,
    aws_secretsmanager as sm,
    aws_rds as rds,
)
from constructs import Construct


@dataclass
class RdsConfig:
    """Config object for CDK App
    max_azs are hardcoded to 2
    """

    region: str  # us-east-1
    vpc_cidr: str  # "10.247.16.0/20"
    public_mask: int  # valid values: 16 through 28
    private_isolated_mask: int  # valid values: 16 through 28
    private_with_egress: int  # valid values: 16 through 28


class RdsStack(Stack):
    """Configure workspaces VPC resources"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # create the RDS VPC
        self.db_vpc = ec2.Vpc(
            self,
            "PublicRdsVpc",
            max_azs=2,
            cidr="10.7.0.0/16",
        )

        # create the DB SG
        self.db_sg = ec2.SecurityGroup(
            self,
            "PublicRdsSecurityGroup",
            vpc=self.db_vpc,
            allow_all_outbound=True,
        )
        # permit inbound access from anywhere
        self.db_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(), ec2.Port.tcp(5432), "PUBLIC POSTGRES ACCESS"
        )

        self.master_secret = sm.Secret(
            self,
            "BootstrapRdsTestRdsMasterSecret",
            generate_secret_string=sm.SecretStringGenerator(
                secret_string_template=json.dumps(
                    {"username": "postgres"}, separators=(",", ":")
                ),
                generate_string_key="password",
                exclude_punctuation=True,
            ),
        )
        engine = rds.DatabaseInstanceEngine.postgres(
            version=rds.PostgresEngineVersion.VER_13_5
        )
        parameter_group = rds.ParameterGroup(
            self,
            "BootstrapRdsTestRdsParameterGroup",
            engine=engine,
            parameters={
                "rds.logical_replication": "1",
                "autovacuum_naptime": "40",
                "rds.allowed_extensions": "dblink, hstore, pg_stat_statements, pglogical",
                "wal_sender_timeout": "0",
                "shared_preload_libraries": "pg_stat_statements, pglogical",
                "pg_stat_statements.track": "ALL",
                "track_activity_query_size": "2048",
            },
        )
        self.instance1 = rds.DatabaseInstance(
            self,
            "BootstrapRdsTestRdsInstance",
            engine=engine,
            publicly_accessible=True,
            parameter_group=parameter_group,
            credentials=rds.Credentials.from_secret(self.master_secret),
            vpc=self.db_vpc,
            allocated_storage=100,
            allow_major_version_upgrade=False,
            auto_minor_version_upgrade=False,
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3, ec2.InstanceSize.SMALL
            ),
            # backup_retention=,
            copy_tags_to_snapshot=True,
            deletion_protection=False,
            enable_performance_insights=True,
            multi_az=False,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_groups=[self.db_sg]
        )
        sm.SecretRotation(
            self,
            "BootstrapRdsTestRdsMasterSecretRotation",
            application=sm.SecretRotationApplication.POSTGRES_ROTATION_SINGLE_USER,
            # Postgres single user scheme
            secret=self.master_secret,
            target=self.instance1,  # a Connectable
            vpc=self.db_vpc,  # The VPC for secret rotation
            exclude_characters=" %+:;\{\}'\"\,@\\",
        )

        self.app_secret = sm.Secret(
            self,
            "BootstrapRdsTestRdsAppSecret",
            generate_secret_string=sm.SecretStringGenerator(
                secret_string_template=json.dumps(
                    {
                        "username": "ctsrw",
                        "dbInstanceIdentifier": self.instance1.instance_identifier,
                        "engine": "postgres",
                        "host": self.instance1.db_instance_endpoint_address,
                        # I would love to use this, but it returns the port as a string
                        # which is inconsistent with the default master generator
                        # and I can't convert to int here
                        # "port": self.instance1.db_instance_endpoint_port,
                        "port": 5432,
                        "masterarn": self.master_secret.secret_arn,
                    },
                    separators=(",", ":"),
                ),
                generate_string_key="password",
                exclude_punctuation=True,
            ),
        )
        sm.SecretRotation(
            self,
            "BootstrapRdsTestRdsAppSecretRotation",
            application=sm.SecretRotationApplication.POSTGRES_ROTATION_MULTI_USER,
            # Postgres single user scheme
            secret=self.app_secret,
            master_secret=self.master_secret,
            target=self.instance1,  # a Connectable
            vpc=self.db_vpc,  # The VPC for secret rotation
            exclude_characters=" %+:;\{\}'\"\,@\\",
        )
