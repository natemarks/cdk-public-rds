#!/usr/bin/env python3
""" demo
sdf
"""

import aws_cdk as cdk

from cdk_public_rds.cdk_public_rds_stack import RdsStack


app = cdk.App()
RdsStack(app, "CdkPublicRdsStack")

app.synth()
