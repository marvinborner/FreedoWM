# -*- coding: utf-8 -*-
from setuptools import setup

try:
    long_description = open("README.md").read()
except IOError:
    long_description = ""

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
    long_description=long_description,
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.7",
    ]
)
