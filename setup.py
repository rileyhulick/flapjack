from setuptools import setup

setup(
    name='flapjack-webstack',
    python_requires='>=3.8',
    version='0.0.1',
    description='No-fuss web stack for localhost development on Linux.',
    url='https://github.com/rileyhulick/flapjack/',
    author='Riley Hulick',
    author_email='rileyhulick@gmail.com',
    license='MIT',
    packages=['flapjack'],
    package_dir={'flapjack': 'src'},
    install_requires=[
            'pyexpander',
        ],
    package_data={
        'flapjack': ['*.conf.in', '*.ini.in'],
    },
    entry_points={
        'console_scripts': [
            'flapjack=flapjack.run:run',
        ],
    },
)
