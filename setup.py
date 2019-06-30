# -*- coding: utf-8 -*-
from setuptools import setup

setup(
    name="FreedoWM",
    version="0.1.dev0",
    description="A free window manager",
    license="BSD",
    author="Marvin Borner",
    install_requires="Xlib",
    py_modules=["freedowm"],
    entry_points={
        'console_scripts': ['freedowm = freedowm', ]
    },
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.7",
    ]
)
