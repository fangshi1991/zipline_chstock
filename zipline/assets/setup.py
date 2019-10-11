from distutils.core import setup,Extension
from Cython.Build import cythonize
import numpy 
setup(
    ext_modules = [Extension('_assets',['_assets.c'],
					include_dirs = [numpy.get_include()]),
	
	], 
      )
setup(
    ext_modules=cythonize('_assets.pyx'),
	include_dirs = [numpy.get_include()]
)