#!/usr/bin/env python3
""" demo
sdf
"""

import aws_cdk as cdk

from cdk_public_rds.cdk_public_rds_stack import RdsStack


app = cdk.App()

# tag all of the resources in the application
cdk.Tags.of(app).add("iac", "cdk-public-rds")
cdk.Tags.of(app).add("owner", "devops")
cdk.Tags.of(app).add("manager", "devops")

RdsStack(app, "CdkPublicRdsStack")

app.synth()
