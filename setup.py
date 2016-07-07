#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pip
from setuptools import setup, find_packages

from gitlab_webhook_receiver import __version__

def get_reqs():
    kwargs = {'session': 'fake session'}
    install_reqs = pip.req.parse_requirements('requirements.pip', **kwargs)
    return [str(ir.req) for ir in install_reqs]


setup(
    name='gitlab-webhook-receiver',
    version=__version__,
    url='git@github.com:dragonkid/gitlab-webhook-receiver.git',
    packages=find_packages(),
    include_package_data=True,
    install_requires=get_reqs(),
    entry_points={
        'console_scripts': [
            'gitlab-webhook-receiver = gitlab_webhook_receiver.receiver:main'
        ]
    }
)
