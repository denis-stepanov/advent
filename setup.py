from setuptools import setup

setup(
    name="advent",
    description="Vent intrusive TV ads",
    url="https://github.com/denis-stepanov/advent",
    license="GNU GPL v3.0",
    author="Denis Stepanov",
    packages=[
        "advent",
        "tv_control",
        "db_djv_pg"
    ],
    entry_points={
        "console_scripts": [
            "advent = advent.advent:main",
            "db-djv-pg = db_djv_pg.db_djv_pg:main"
        ]
    },
    install_requires=[
        'PyDejavu',
        'psycopg2',
        'requests',
    ],
)
