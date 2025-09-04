#!/usr/bin/env python3
"""
VRChat OSC Client Setup Script
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="vrchat-osc-client",
    version="2.0.0",
    author="Musashino",
    description="VRChat OSC通信工具 - 支持文字和语音传输",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/musashino/vrchat-osc-client",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Communications :: Chat",
        "Topic :: Games/Entertainment",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "vrchat-osc-gui=main:main",
        ],
    },
    keywords="vrchat osc communication voice text",
    project_urls={
        "Bug Reports": "https://github.com/musashino/vrchat-osc-client/issues",
        "Source": "https://github.com/musashino/vrchat-osc-client",
    },
)