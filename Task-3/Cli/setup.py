from setuptools import setup, find_packages

setup(
    name="insighta",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "typer==0.12.3",
        "rich==13.7.1",
        "httpx==0.28.1",
    ],
    entry_points={
        "console_scripts": [
            "insighta=insighta.main:app",
        ],
    },
    python_requires=">=3.11",
)