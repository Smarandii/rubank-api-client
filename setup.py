from setuptools import setup, find_packages

setup(
    name="rubank_api_client",
    version="1.0.0",
    description="A Python client for interacting with Sber Bank's online services.",
    author="Smarandii",
    packages=find_packages(),
    install_requires=[
        "requests",
        "selenium",
        "pandas"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
