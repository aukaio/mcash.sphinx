from setuptools import setup, find_packages


setup(
    name='mcash.sphinx',
    version='1.0',
    author="mCASH Team",
    author_email="support@mca.sh",
    description="mCASH Sphinx modules",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'sphinx'
    ],
    namespace_packages=['mcash']
)
