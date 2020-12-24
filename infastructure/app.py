#!/usr/bin/env python3

from aws_cdk import core

from infastructure.infastructure_stack import InfastructureStack


app = core.App()
InfastructureStack(app, "infastructure")

app.synth()
