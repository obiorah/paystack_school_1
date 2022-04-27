from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in paystack_school/__init__.py
from paystack_school import __version__ as version

setup(
	name="paystack_school",
	version=version,
	description="Paystack for Schools",
	author="Odera",
	author_email="okonkwooderao@gmail.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
