
from distutils.core import setup

setup(name='mrchecker',
      version='1.0.0',
      description='Portable raid health check script',
      author='Hunter Matthews',
      author_email='hunter@pobox.com',
      url='http://nowebsiteyet.com',
      package_dir = {'': 'lib'},
      packages=['raid_check'],
      scripts=['scripts/raid-check'],
      )


## END OF LINE ##
