from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# name should match your app name
setup(
    name="lisec",
    version='0.0.1',
    description="Lisec Integration for ERPNext",
    author="Ronoh",
    author_email="elisha@aqiqsolutions.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires
) 