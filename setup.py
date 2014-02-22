from setuptools import setup, find_packages


setup(
    name='mcash.sphinx',
    version='0.2',
    author="mCASH Team",
    author_email="support@mca.sh",
    description="mCASH Sphinx modules",
    packages=find_packages('mcash.sphinx'),
    package_dir = {'': 'mcash.sphinx'},
    include_package_data=True,
    install_requires=[
        'sphinx'
    ],
    namespace_packages=['mcash'],
    zip_safe=True,
)
