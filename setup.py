from pkg_resources import parse_version
from configparser import ConfigParser
import setuptools
assert parse_version(setuptools.__version__)>=parse_version('36.2')

# note: all settings are in settings.ini; edit there, not here
config = ConfigParser(delimiters=['='])
config.read('settings.ini')
cfg = config['DEFAULT']

cfg_keys = 'version description keywords author author_email'.split()
expected = cfg_keys + "lib_name user branch license status min_python audience language packages tested_pythons".split()
for o in expected: assert o in cfg, "missing expected setting: {}".format(o)
setup_cfg = {o:cfg[o] for o in cfg_keys}

licenses = {
    'apache2': ('Apache Software License 2.0','OSI Approved :: Apache Software License'),
}
statuses = [ '1 - Planning', '2 - Pre-Alpha', '3 - Alpha',
    '4 - Beta', '5 - Production/Stable', '6 - Mature', '7 - Inactive' ]
# Classifiers name only the Python versions that make release-check installs the wheel on
# (vps-0ax); min_python must be the lowest of them.
py_versions = cfg['tested_pythons'].split()

requirements = cfg.get('requirements','').split()
lic = licenses[cfg['license']]
min_python = cfg['min_python']
assert min_python == min(py_versions, key=lambda v: tuple(map(int, v.split('.')))), \
    "min_python must be the lowest of tested_pythons"
# Ship only the listed packages (vps-0ax): find_packages() also picked up leftovers.
packages = cfg['packages'].split()

setuptools.setup(
    name = cfg['lib_name'],
    license = lic[0],
    classifiers = [
        'Development Status :: ' + statuses[int(cfg['status'])],
        'Intended Audience :: ' + cfg['audience'].title(),
        'License :: ' + lic[1],
        'Natural Language :: ' + cfg['language'].title(),
    ] + ['Programming Language :: Python :: 3'] + ['Programming Language :: Python :: '+o for o in py_versions],
    url = cfg['git_url'],
    packages = setuptools.find_packages(include=packages + [p + '.*' for p in packages]),
    include_package_data = True,
    install_requires = requirements,
    dependency_links = cfg.get('dep_links','').split(),
    python_requires  = '>=' + cfg['min_python'],
    long_description = open('README.md').read(),
    long_description_content_type = 'text/markdown',
    zip_safe = False,
    entry_points = { 'console_scripts': cfg.get('console_scripts','').split() },
    **setup_cfg)

