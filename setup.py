"""
Setup script for Racoon Lab Feed Manager
"""
from setuptools import setup, find_packages

setup(
    name='racoon-feed-manager',
    version='4.0.0',
    packages=find_packages(),
    install_requires=[
        'flask>=3.0.0',
        'requests>=2.31.0',
        'gunicorn>=21.2.0',
    ],
    python_requires='>=3.11',
)
