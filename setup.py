import sys
from setuptools import setup, find_packages

long_description = ""
with open("README.md", "r") as file:
    long_description = file.read()

install_requires = ["starkbank-ecdsa==2.0.3"]
if sys.platform == 'win32':
    install_requires += [
        "pypiwin32==223",
        "pywin32==304"
    ]

setup(
    name="pbcoin",
    version="0.0.1",
    description="A simple blockchain with python",
    license = "MIT",
    long_description_content_type="text/markdown",
    url="https://github.com/Esmokes17/pbcoin.git",
    author="Mahdi Kashani",
    packages=find_packages(),
    python_requires=">=3.8, <4",
    install_requires=[install_requires],

    entry_points={
        'console_scripts': [
            'node=node:main',
            'pbcoin_cli=pbcoin_cli:cli'
        ]
    }
)
